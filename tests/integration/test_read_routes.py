"""Run against a running API: uv run pytest -m integration"""

import uuid

import pytest

pytestmark = pytest.mark.integration


def test_catalog_has_fixed_prices(client):
    r = client.get("/api/v1/catalog")
    assert r.status_code == 200
    prices = {p["sku"]: p["unit_price_cents"] for p in r.json()["products"]}
    assert prices == {"KIT-100": 1299, "PART-200": 599, "PACK-300": 249}


def test_inventory_is_nonnegative_integer(client):
    r = client.get("/api/v1/inventory/KIT-100")
    assert r.status_code == 200
    body = r.json()
    assert body["sku"] == "KIT-100"
    assert type(body["available"]) is int and body["available"] >= 0


def test_unknown_sku_returns_404(client):
    r = client.get("/api/v1/inventory/NOPE-999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "SKU_NOT_FOUND"


@pytest.mark.parametrize("order_id", ["not-real-order", str(uuid.uuid4())])
def test_unknown_order_returns_404(client, order_id):
    r = client.get(f"/api/v1/orders/{order_id}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ORDER_NOT_FOUND"
