"""Processing one claimed job: complete it, or schedule a retry, or dead-letter it."""

from __future__ import annotations

import random
import time
from collections.abc import Callable

import psycopg
from psycopg_pool import ConnectionPool

from common.config import Settings
from common.logging import log_event
from worker.claims import Job

POISON_CUSTOMER_ID = "POISON-TEST"


class ProcessingError(Exception):
    """An expected failure whose message is safe to store in jobs.last_error."""


def is_poison(customer_id: str, settings: Settings) -> bool:
    """Deliberate failure for the poison-job drill. Never active unless explicitly enabled."""
    return settings.poison_test_mode and customer_id == POISON_CUSTOMER_ID


def compute_backoff(
    attempt: int, base: float, cap: float, rand: Callable[[], float] = random.random
) -> float:
    """Exponential backoff with up to 10 % jitter: base, 2*base, 4*base ... capped at `cap`.

    Jitter spreads retries out so failing jobs do not all retry at the same instant.
    """
    delay = min(cap, base * (2 ** max(attempt - 1, 0)))
    return delay + delay * 0.1 * rand()


def complete_order(conn: psycopg.Connection, job: Job, worker_id: str) -> bool:
    """Finish the order exactly once. Returns False if this worker no longer owns the job.

    Call inside a transaction. The receipts primary key is the last line of defence:
    even if two workers got here for the same order, only one receipt can exist.
    """
    owned = conn.execute(
        """
        SELECT 1 FROM jobs
        WHERE job_id = %s AND status = 'processing' AND locked_by = %s
        FOR UPDATE
        """,
        (job.job_id, worker_id),
    ).fetchone()
    if owned is None:
        return False  # lease expired and another worker took over: let it finish
    conn.execute(
        """
        INSERT INTO receipts (order_id, completed_by) VALUES (%s, %s)
        ON CONFLICT (order_id) DO NOTHING
        """,
        (job.order_id, worker_id),
    )
    conn.execute(
        """
        UPDATE orders SET status = 'completed', completed_at = now(), updated_at = now()
        WHERE order_id = %s
        """,
        (job.order_id,),
    )
    conn.execute(
        """
        UPDATE jobs SET status = 'done', locked_by = NULL, locked_until = NULL,
                        last_error = NULL, updated_at = now()
        WHERE job_id = %s
        """,
        (job.job_id,),
    )
    return True


def record_failure(
    conn: psycopg.Connection, job: Job, error: str, settings: Settings, worker_id: str
) -> str:
    """Schedule a retry, or dead-letter the job after max_attempts. Returns the new status.

    Stock is NOT released for a failed order: it stays reserved for operator review.
    """
    if job.attempts >= job.max_attempts:
        updated = conn.execute(
            """
            UPDATE jobs SET status = 'dead', locked_by = NULL, locked_until = NULL,
                            last_error = %s, updated_at = now()
            WHERE job_id = %s AND status = 'processing' AND locked_by = %s
            """,
            (error, job.job_id, worker_id),
        )
        if updated.rowcount:
            conn.execute(
                "UPDATE orders SET status = 'failed', updated_at = now() WHERE order_id = %s",
                (job.order_id,),
            )
        return "dead"

    delay = compute_backoff(
        job.attempts, settings.worker_backoff_base_seconds, settings.worker_backoff_max_seconds
    )
    updated = conn.execute(
        """
        UPDATE jobs SET status = 'queued', locked_by = NULL, locked_until = NULL,
                        next_attempt_at = now() + make_interval(secs => %s),
                        last_error = %s, updated_at = now()
        WHERE job_id = %s AND status = 'processing' AND locked_by = %s
        """,
        (delay, error, job.job_id, worker_id),
    )
    if updated.rowcount:
        conn.execute(
            "UPDATE orders SET status = 'queued', updated_at = now() WHERE order_id = %s",
            (job.order_id,),
        )
    return f"retry in {delay:.1f}s"


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, ProcessingError):
        return str(exc)[:200]
    return type(exc).__name__  # unknown errors: type only, the message may contain data


def process_job(pool: ConnectionPool, job: Job, settings: Settings) -> None:
    worker_id = settings.worker_id
    ids = {"order_id": str(job.order_id), "job_id": str(job.job_id), "attempt": job.attempts}
    log_event("job_reclaimed" if job.reclaimed else "job_claimed", worker_id=worker_id, **ids)
    try:
        if job.attempts > job.max_attempts:
            raise ProcessingError("lease expired during the final attempt")
        if is_poison(job.customer_id, settings):
            raise ProcessingError("poison test order (POISON_TEST_MODE)")

        time.sleep(settings.worker_processing_delay_seconds)  # simulated fulfilment work

        with pool.connection() as conn, conn.transaction():
            finished = complete_order(conn, job, worker_id)
        if finished:
            log_event("order_completed", worker_id=worker_id, **ids)
        else:
            log_event("job_lease_lost", level="warning", worker_id=worker_id, **ids)
    except Exception as exc:  # noqa: BLE001 - every failure must be recorded, never crash
        error = _safe_error(exc)
        try:
            with pool.connection() as conn, conn.transaction():
                outcome = record_failure(conn, job, error, settings, worker_id)
        except Exception as db_exc:  # noqa: BLE001
            # Database unreachable: the lease will expire and another worker retries.
            log_event(
                "job_failure_not_recorded",
                level="error",
                worker_id=worker_id,
                error_type=type(db_exc).__name__,
                **ids,
            )
            return
        event = "job_dead" if outcome == "dead" else "job_retry_scheduled"
        log_event(
            event,
            level="error" if outcome == "dead" else "warning",
            worker_id=worker_id,
            error=error,
            next=outcome,
            **ids,
        )
