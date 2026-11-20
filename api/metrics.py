"""Prometheus metrics for GET /metrics (text exposition format).

Two kinds of numbers:
- HTTP metrics (requests, latency) are counted inside each API process.
- Business totals (orders created/completed/failed, worker retries) are READ FROM POSTGRES
  at scrape time by BusinessCollector. The worker is another process, so an in-memory
  counter in the API could never see its work; the database is the shared truth, and
  every API replica reports the same correct value.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from prometheus_client.core import CounterMetricFamily
from prometheus_client.registry import Collector
from psycopg_pool import ConnectionPool

from common.logging import log_event

REGISTRY = CollectorRegistry(auto_describe=True)

HTTP_REQUESTS = Counter(
    "fulfillops_http_requests_total",
    "HTTP requests handled, by method, route template and status code.",
    ["method", "route", "status"],
    registry=REGISTRY,
)
HTTP_LATENCY = Histogram(
    "fulfillops_http_request_duration_seconds",
    "HTTP request duration in seconds, by method and route template.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    registry=REGISTRY,
)

_BUSINESS_SQL = """
SELECT
    (SELECT count(*) FROM orders),
    (SELECT count(*) FROM receipts),
    (SELECT count(*) FROM orders WHERE status = 'failed'),
    (SELECT coalesce(sum(greatest(attempts - 1, 0)), 0) FROM jobs)
"""


class BusinessCollector(Collector):
    """Reads business totals from Postgres each time /metrics is scraped."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def collect(self) -> Iterator[CounterMetricFamily]:
        try:
            with self._pool.connection(timeout=2) as conn:
                created, completed, failed, retries = conn.execute(_BUSINESS_SQL).fetchone()
        except Exception as exc:  # noqa: BLE001 - DB down: HTTP metrics are still served
            log_event("metrics_db_unavailable", level="warning", error_type=type(exc).__name__)
            return
        for name, doc, value in (
            ("fulfillops_orders_created", "Orders accepted (committed).", created),
            ("fulfillops_orders_completed", "Orders completed by a worker.", completed),
            ("fulfillops_orders_failed", "Orders dead-lettered after max retries.", failed),
            ("fulfillops_worker_retries", "Job attempts beyond the first.", retries),
        ):
            # CounterMetricFamily adds the _total suffix: fulfillops_orders_created_total
            yield CounterMetricFamily(name, doc, value=int(value))


def install_business_collector(pool: ConnectionPool) -> None:
    REGISTRY.register(BusinessCollector(pool))


router = APIRouter()


@router.get("/metrics")
def metrics(_: Request) -> Response:
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
