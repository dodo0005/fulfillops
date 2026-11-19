"""Order creation through the real API. These tests CONSUME TEST STOCK.

Run scripts/reset-test-data.sh first, and only against the isolated test database.
"""

import uuid

import pytest

pytestmark = pytest.mark.integration

URL = "/api/v1/orders"


def new_key() -> str:
    return "it-" + uuid.uuid4().hex


def stock(client, sku: str) -> int:
    return client.get(f"/api/v1/inventory/{sku}").json()["available"]


def post(client, payload: dict, key: str):
    return client.post(URL, json=payload, headers={"Idempotency-Key": key})


def test_create_then_replay_reserves_once(client):
    payload = {"customer_id": "CUST-IT", "items": [{"sku": "KIT-100", "quantity": 1}]}
    key = new_key()
    before = stock(client, "KIT-100")

    first = post(client, payload, key)
    assert first.status_code == 202
    assert first.json()["status"] == "queued"
    order_id = first.json()["order_id"]

    again = post(client, payload, key)
    assert again.status_code == 202
    assert again.json() == {"order_id": order_id, "status": "queued"}
    assert stock(client, "KIT-100") == before - 1  # reserved once, not twice

    order = client.get(f"/api/v1/orders/{order_id}").json()
    assert order["total_cents"] == 1299
    assert order["status"] in {"queued", "processing", "completed"}


def test_same_key_different_payload_conflicts(client):
    key = new_key()
    payload = {"customer_id": "CUST-IT", "items": [{"sku": "PART-200", "quantity": 1}]}
    assert post(client, payload, key).status_code == 202
    before = stock(client, "PART-200")

    other = {"customer_id": "CUST-OTHER", "items": [{"sku": "PART-200", "quantity": 1}]}
    r = post(client, other, key)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert stock(client, "PART-200") == before


def test_out_of_stock_changes_nothing(client):
    before = stock(client, "KIT-100")
    payload = {"customer_id": "CUST-IT", "items": [{"sku": "KIT-100", "quantity": 20}]}
    r = post(client, payload, new_key())
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "OUT_OF_STOCK"
    assert stock(client, "KIT-100") == before


def test_out_of_stock_on_second_line_rolls_back_first_line(client):
    kit, part = stock(client, "KIT-100"), stock(client, "PART-200")
    payload = {
        "customer_id": "CUST-IT",
        "items": [{"sku": "KIT-100", "quantity": 1}, {"sku": "PART-200", "quantity": 20}],
    }
    r = post(client, payload, new_key())
    assert r.status_code == 409
    assert (stock(client, "KIT-100"), stock(client, "PART-200")) == (kit, part)  # no partial
