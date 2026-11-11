"""Validation through the real API. None of these requests creates an order."""

import uuid

import pytest

pytestmark = pytest.mark.integration

URL = "/api/v1/orders"
GOOD = {"customer_id": "CUST-042", "items": [{"sku": "KIT-100", "quantity": 1}]}


def key() -> dict:
    return {"Idempotency-Key": "val-" + uuid.uuid4().hex}


def error_code(response) -> str:
    return response.json()["error"]["code"]


def test_missing_key(client):
    r = client.post(URL, json=GOOD)
    assert r.status_code == 400 and error_code(r) == "IDEMPOTENCY_REQUIRED"


def test_invalid_json(client):
    r = client.post(URL, content=b"{oops", headers={**key(), "Content-Type": "application/json"})
    assert r.status_code == 400 and error_code(r) == "INVALID_JSON"


def test_invalid_structure(client):
    r = client.post(URL, json={"customer_id": "CUST-042", "items": []}, headers=key())
    assert r.status_code == 400 and error_code(r) == "INVALID_REQUEST"


@pytest.mark.parametrize("qty", [0, 21, True])
def test_invalid_quantity(client, qty):
    payload = {"customer_id": "CUST-042", "items": [{"sku": "KIT-100", "quantity": qty}]}
    r = client.post(URL, json=payload, headers=key())
    assert r.status_code == 422 and error_code(r) == "INVALID_QUANTITY"


def test_unknown_sku(client):
    payload = {"customer_id": "CUST-042", "items": [{"sku": "NOPE-999", "quantity": 1}]}
    r = client.post(URL, json=payload, headers=key())
    assert r.status_code == 422 and error_code(r) == "INVALID_SKU"


def test_body_too_large(client):
    payload = {"customer_id": "CUST-042", "items": GOOD["items"], "pad": "x" * 17000}
    r = client.post(URL, json=payload, headers=key())
    assert r.status_code == 413 and error_code(r) == "PAYLOAD_TOO_LARGE"
