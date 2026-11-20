"""Claiming jobs from the Postgres `jobs` table.

FOR UPDATE SKIP LOCKED lets several workers poll the same table without ever taking
the same job: a row locked by one worker is simply skipped by the others.
A claim is a lease: if the worker dies, `locked_until` passes and another worker
reclaims the job (see docs/ADR-001.md).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class Job:
    job_id: uuid.UUID
    order_id: uuid.UUID
    customer_id: str
    attempts: int  # already counts this attempt
    max_attempts: int
    reclaimed: bool  # True if a previous worker died while holding it


_CLAIM_NEXT = """
WITH next AS (
    SELECT j.job_id, j.status AS prev_status, o.customer_id
    FROM jobs j
    JOIN orders o ON o.order_id = j.order_id
    WHERE (j.status = 'queued' AND j.next_attempt_at <= now())
       OR (j.status = 'processing' AND j.locked_until < now())
    ORDER BY j.created_at
    FOR UPDATE OF j SKIP LOCKED
    LIMIT 1
)
UPDATE jobs j
SET status = 'processing',
    attempts = j.attempts + 1,
    locked_by = %(worker)s,
    locked_until = now() + make_interval(secs => %(lease)s),
    updated_at = now()
FROM next
WHERE j.job_id = next.job_id
RETURNING j.job_id, j.order_id, next.customer_id, j.attempts, j.max_attempts,
          next.prev_status
"""


def claim_next_job(conn: psycopg.Connection, worker_id: str, lease_s: int) -> Job | None:
    """Claim the oldest runnable job, or return None if there is nothing to do.

    Call inside a transaction; the order is marked `processing` in the same one.
    """
    row = conn.execute(_CLAIM_NEXT, {"worker": worker_id, "lease": lease_s}).fetchone()
    if row is None:
        return None
    job_id, order_id, customer_id, attempts, max_attempts, prev_status = row
    conn.execute(
        "UPDATE orders SET status = 'processing', updated_at = now() WHERE order_id = %s",
        (order_id,),
    )
    return Job(
        job_id=job_id,
        order_id=order_id,
        customer_id=customer_id,
        attempts=attempts,
        max_attempts=max_attempts,
        reclaimed=prev_status == "processing",
    )
