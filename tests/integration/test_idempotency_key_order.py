"""Same payload with JSON keys in a different order must count as the same request.

This is also the red-to-green bug test for task A11.
"""

import json
import uuid

import pytest

pytestmark = pytest.mark.integration


def test_reordered_json_keys_replay_same_order(client):
    key = "order-" + uuid.uuid4().hex
    headers = {"Idempotency-Key": key, "Content-Type": "application/json"}
    first = json.dumps({"customer_id": "CUST-ORD", "items": [{"sku": "PART-200", "quantity": 1}]})
    second = json.dumps({"items": [{"quantity": 1, "sku": "PART-200"}], "customer_id": "CUST-ORD"})

    a = client.post("/api/v1/orders", content=first, headers=headers)
    b = client.post("/api/v1/orders", content=second, headers=headers)
    assert a.status_code == 202
    assert b.status_code == 202, b.text
    assert b.json()["order_id"] == a.json()["order_id"]
