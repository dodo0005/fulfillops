"""Race tests hit the API over HTTP from many threads at once. They CONSUME TEST STOCK.

Run against the isolated test stack only, right after a reset:
  bash scripts/reset-test-data.sh && uv run pytest -m race -v
FULFILLOPS_URLS lists the API replicas, comma-separated (two for the cross-replica test).
"""

import os

import httpx
import pytest


@pytest.fixture(scope="session")
def base_urls() -> list[str]:
    raw = os.environ.get("FULFILLOPS_URLS") or os.environ.get(
        "FULFILLOPS_BASE_URL", "http://localhost:8080"
    )
    return [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]


@pytest.fixture(scope="session")
def client(base_urls) -> httpx.Client:
    with httpx.Client(base_url=base_urls[0], timeout=15) as c:
        yield c
