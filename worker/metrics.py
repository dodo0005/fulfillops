"""Worker-side metrics on :WORKER_METRICS_PORT/metrics (per worker process)."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, start_http_server

from common.logging import log_event

REGISTRY = CollectorRegistry(auto_describe=True)

JOBS_COMPLETED = Counter(
    "fulfillops_jobs_completed_total",
    "Jobs completed by this worker.",
    ["worker"],
    registry=REGISTRY,
)
JOBS_RETRIED = Counter(
    "fulfillops_jobs_retried_total",
    "Failed attempts scheduled for retry.",
    ["worker"],
    registry=REGISTRY,
)
JOBS_DEAD = Counter(
    "fulfillops_jobs_dead_total",
    "Jobs dead-lettered after max attempts.",
    ["worker"],
    registry=REGISTRY,
)
JOBS_RECLAIMED = Counter(
    "fulfillops_jobs_reclaimed_total",
    "Jobs taken over after another worker's lease expired.",
    ["worker"],
    registry=REGISTRY,
)


def start_metrics_server(port: int) -> None:
    """Never fatal: a busy port (two workers on one laptop) only loses worker metrics."""
    try:
        start_http_server(port, registry=REGISTRY)
        log_event("worker_metrics_listening", port=port)
    except OSError as exc:
        log_event(
            "worker_metrics_unavailable", level="warning", port=port, error_type=type(exc).__name__
        )
