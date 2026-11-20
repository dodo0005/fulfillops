"""Duplicate SKU lines are added together before reserving and billing."""

import time
import uuid

import pytest

pytestmark = pytest.mark.integration

SKU = "PACK-300"


def test_duplicate_lines_reserve_and_bill_the_sum(client):
    before = client.get(f"/api/v1/inventory/{SKU}").json()["available"]
    if before < 4:
        pytest.skip(f"{SKU} needs 4 units: run scripts/reset-test-data.sh first")
    payload = {
        "customer_id": "CUST-MULTI",
        "items": [{"sku": SKU, "quantity": 2}, {"sku": SKU, "quantity": 2}],
    }
    r = client.post(
        "/api/v1/orders", json=payload, headers={"Idempotency-Key": "multi-" + uuid.uuid4().hex}
    )
    assert r.status_code == 202
    assert client.get(f"/api/v1/inventory/{SKU}").json()["available"] == before - 4

    order_id = r.json()["order_id"]
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        order = client.get(f"/api/v1/orders/{order_id}").json()
        if order["status"] == "completed":
            break
        time.sleep(0.3)
    assert order["status"] == "completed", "is the worker running?"
    assert order["total_cents"] == 4 * 249
