"""Pure validation for POST /api/v1/orders. No database access here.

Checks run in the order fixed by section 5 of docs/team-guide.md (first failure wins).
The body-size check (step 1) is in api/middleware.py; the SKU check (step 6) needs the
catalog, so it is done by check_known_skus() with the SKUs read from the database.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from api.errors import ApiError

KEY_MIN, KEY_MAX = 8, 128
MAX_CUSTOMER_ID = 64
MAX_ITEMS = 10
MIN_QTY, MAX_QTY = 1, 20


@dataclass(frozen=True)
class OrderRequest:
    customer_id: str
    items: list[tuple[str, int]]  # lines exactly as sent
    lines: dict[str, int]  # duplicate SKUs added together, sorted by SKU
    request_hash: str  # SHA-256 of the canonical JSON body


def validate_idempotency_key(value: str | None) -> str:
    """Step 2. Missing or empty -> 400 IDEMPOTENCY_REQUIRED; malformed -> 400 INVALID_REQUEST."""
    if value is None or value == "":
        raise ApiError(400, "IDEMPOTENCY_REQUIRED", "Idempotency-Key header is required")
    printable_ascii = all(32 <= ord(ch) <= 126 for ch in value)
    if not (KEY_MIN <= len(value) <= KEY_MAX) or not printable_ascii:
        raise ApiError(
            400, "INVALID_REQUEST", "Idempotency-Key must be 8-128 printable ASCII characters"
        )
    return value


def canonical_hash(body: dict) -> str:
    """Same payload with keys in a different order -> same hash."""
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def aggregate_lines(items: list[tuple[str, int]]) -> dict[str, int]:
    """[("PACK-300", 2), ("PACK-300", 2)] -> {"PACK-300": 4}, keys sorted.

    Sorted order matters: the reservation locks rows in this order, which avoids deadlocks.
    """
    totals: dict[str, int] = {}
    for sku, qty in items:
        totals[sku] = totals.get(sku, 0) + qty
    return dict(sorted(totals.items()))


def _is_valid_quantity(value: object) -> bool:
    # type(...) is int rejects True/False (bool is a subclass of int) and 1.0
    return type(value) is int and MIN_QTY <= value <= MAX_QTY


def parse_order_request(raw: bytes) -> OrderRequest:
    """Steps 3-5: JSON, structure, quantities."""
    # Step 3: valid JSON
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ApiError(400, "INVALID_JSON", "Request body is not valid JSON") from None

    # Step 4: structure
    if not isinstance(body, dict):
        raise ApiError(400, "INVALID_REQUEST", "Request body must be a JSON object")
    customer_id = body.get("customer_id")
    if (
        not isinstance(customer_id, str)
        or not customer_id.strip()
        or len(customer_id) > MAX_CUSTOMER_ID
    ):
        raise ApiError(400, "INVALID_REQUEST", "customer_id must be a string of 1-64 characters")
    items = body.get("items")
    if not isinstance(items, list) or not (1 <= len(items) <= MAX_ITEMS):
        raise ApiError(400, "INVALID_REQUEST", "items must be an array of 1-10 objects")
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("sku"), str) or not item["sku"]:
            raise ApiError(400, "INVALID_REQUEST", "each item needs a sku string")

    # Step 5: quantities (checked for every line before any SKU check)
    for item in items:
        if not _is_valid_quantity(item.get("quantity")):
            raise ApiError(422, "INVALID_QUANTITY", "quantity must be an integer from 1 to 20")

    parsed_items = [(item["sku"], item["quantity"]) for item in items]
    return OrderRequest(
        customer_id=customer_id,
        items=parsed_items,
        lines=aggregate_lines(parsed_items),
        request_hash=canonical_hash(body),
    )


def check_known_skus(order: OrderRequest, known_skus: set[str]) -> None:
    """Step 6: every SKU must exist in the catalog."""
    if any(sku not in known_skus for sku in order.lines):
        raise ApiError(422, "INVALID_SKU", "Unknown SKU in order")
