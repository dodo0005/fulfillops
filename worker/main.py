"""Worker process. Start with: python -m worker.main

Polls Postgres for jobs (QUEUE_BACKEND=postgres). Redis wake-ups are added in task A9.
SIGTERM/SIGINT: finish the current job, then exit (Kubernetes rolling restarts rely on it).
"""

from __future__ import annotations

import signal
import sys
import threading

from psycopg_pool import ConnectionPool

from common.config import Settings, load_settings
from common.db import create_pool
from common.logging import configure_logging, log_event
from worker.claims import claim_next_job
from worker.metrics import start_metrics_server
from worker.processor import process_job


def run_loop(settings: Settings, pool: ConnectionPool, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            with pool.connection() as conn, conn.transaction():
                job = claim_next_job(conn, settings.worker_id, settings.worker_lease_seconds)
        except Exception as exc:  # noqa: BLE001 - database down: wait and try again
            log_event("worker_db_unavailable", level="warning", error_type=type(exc).__name__)
            stop_event.wait(settings.worker_poll_interval_seconds)
            continue

        if job is None:
            stop_event.wait(settings.worker_poll_interval_seconds)  # nothing to do
        else:
            process_job(pool, job, settings)  # then immediately look for the next one


def main() -> int:
    settings = load_settings()
    configure_logging("worker", settings.log_level)
    stop_event = threading.Event()

    def _stop(signum: int, _frame: object) -> None:
        log_event("worker_stopping", signal=signal.Signals(signum).name)
        stop_event.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    start_metrics_server(settings.worker_metrics_port)
    pool = create_pool(settings, min_size=1, max_size=2)
    pool.open(wait=False)
    log_event(
        "worker_started",
        worker_id=settings.worker_id,
        queue_backend=settings.queue_backend,
        max_attempts=settings.worker_max_attempts,
        lease_seconds=settings.worker_lease_seconds,
    )
    try:
        run_loop(settings, pool, stop_event)
    finally:
        pool.close()
        log_event("worker_stopped", worker_id=settings.worker_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
