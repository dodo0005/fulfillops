import pytest

pytestmark = pytest.mark.integration

REQUIRED = [
    "fulfillops_orders_created_total",
    "fulfillops_orders_completed_total",
    "fulfillops_orders_failed_total",
    "fulfillops_worker_retries_total",
    "fulfillops_http_requests_total",
    "fulfillops_http_request_duration_seconds_bucket",
]


def test_metrics_exposes_required_series(client):
    client.get("/api/v1/catalog")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    for name in REQUIRED:
        assert name in r.text, name
    assert "CUST-" not in r.text  # no customer IDs in labels
