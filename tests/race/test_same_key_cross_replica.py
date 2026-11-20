"""Gate 1: the same Idempotency-Key sent 8 times at once, spread over 2 API replicas,
creates ONE order and reserves stock ONCE. Works across processes because the guard is
the database's UNIQUE(idempotency_key), not anything in Python memory."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

pytestmark = pytest.mark.race

SKU = "KIT-100"
COPIES = 8


def test_same_key_across_replicas_reserves_once(client, base_urls):
    if len(base_urls) < 2:
        pytest.skip("set FULFILLOPS_URLS to two API replicas, e.g. :8080,:8081")
    before = client.get(f"/api/v1/inventory/{SKU}").json()["available"]
    if before < 1:
        pytest.skip(f"{SKU} has no stock: run scripts/reset-test-data.sh first")

    key = "shared-" + uuid.uuid4().hex
    body = {"customer_id": "CUST-SHARED", "items": [{"sku": SKU, "quantity": 1}]}
    start_line = threading.Barrier(COPIES)

    def send(i: int) -> tuple[int, str, str]:
        url = base_urls[i % len(base_urls)]  # alternate replicas: 4 requests each
        start_line.wait()
        r = httpx.post(
            url + "/api/v1/orders", json=body, headers={"Idempotency-Key": key}, timeout=30
        )
        return r.status_code, r.json().get("order_id"), url

    with ThreadPoolExecutor(max_workers=COPIES) as pool:
        results = list(pool.map(send, range(COPIES)))

    assert [s for s, _, _ in results] == [202] * COPIES, results
    assert len({oid for _, oid, _ in results}) == 1, "same key created several orders"
    assert len({url for _, _, url in results}) == 2, "both replicas must have been used"
    after = client.get(f"/api/v1/inventory/{SKU}").json()["available"]
    assert after == before - 1, "stock must be reserved exactly once"
