"""More buyers than stock, all at the same instant: no overselling, stock ends at exactly 0."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

pytestmark = pytest.mark.race

SKU = "PART-200"
EXTRA_BUYERS = 5


def test_more_buyers_than_stock_never_oversells(client, base_urls):
    available = client.get(f"/api/v1/inventory/{SKU}").json()["available"]
    if available < 1:
        pytest.skip(f"{SKU} has no stock: run scripts/reset-test-data.sh first")

    buyers = available + EXTRA_BUYERS
    start_line = threading.Barrier(buyers)  # every thread fires at the same moment

    def buy(i: int) -> int:
        url = base_urls[i % len(base_urls)] + "/api/v1/orders"
        body = {"customer_id": f"CUST-RACE-{i}", "items": [{"sku": SKU, "quantity": 1}]}
        start_line.wait()
        r = httpx.post(
            url, json=body, headers={"Idempotency-Key": "race-" + uuid.uuid4().hex}, timeout=30
        )
        return r.status_code

    with ThreadPoolExecutor(max_workers=buyers) as pool:
        statuses = list(pool.map(buy, range(buyers)))

    assert set(statuses) <= {202, 409}, statuses
    assert statuses.count(202) == available  # every unit sold exactly once
    assert statuses.count(409) == EXTRA_BUYERS  # everyone else told OUT_OF_STOCK
    assert client.get(f"/api/v1/inventory/{SKU}").json()["available"] == 0
