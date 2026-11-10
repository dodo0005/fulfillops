import os

import httpx
import pytest


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    base_url = os.environ.get("FULFILLOPS_BASE_URL", "http://localhost:8080")
    with httpx.Client(base_url=base_url, timeout=10) as c:
        yield c
