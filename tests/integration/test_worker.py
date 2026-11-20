"""Needs a worker running next to the API (Compose does this; locally: python -m worker.main)."""

import time
import uuid

import pytest

pytestmark = pytest.mark.integration


def wait_for_status(client, order_id: str, timeout: float = 15) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        order = client.get(f"/api/v1/orders/{order_id}").json()
        if order["status"] in {"completed", "failed"}:
            return order
        assert order["status"] in {"queued", "processing"}
        time.sleep(0.3)
    raise AssertionError("order did not finish within 15 seconds; is the worker running?")


def test_worker_completes_order_with_correct_total(client):
    payload = {
        "customer_id": "CUST-WORKER",
        "items": [{"sku": "PART-200", "quantity": 1}, {"sku": "PART-200", "quantity": 1}],
    }
    r = client.post(
        "/api/v1/orders", json=payload, headers={"Idempotency-Key": "wk-" + uuid.uuid4().hex}
    )
    assert r.status_code == 202
    order = wait_for_status(client, r.json()["order_id"])
    assert order["status"] == "completed"
    assert order["total_cents"] == 2 * 599
