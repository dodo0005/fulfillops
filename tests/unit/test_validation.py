import json

import pytest

from api.errors import ApiError
from api.validation import (
    aggregate_lines,
    canonical_hash,
    check_known_skus,
    parse_order_request,
    validate_idempotency_key,
)

KNOWN = {"KIT-100", "PART-200", "PACK-300"}


def body(**overrides) -> bytes:
    data = {"customer_id": "CUST-042", "items": [{"sku": "KIT-100", "quantity": 1}]}
    data.update(overrides)
    return json.dumps(data).encode()


def code_of(fn, *args) -> tuple[int, str]:
    with pytest.raises(ApiError) as err:
        fn(*args)
    return err.value.status, err.value.code


# --- Idempotency-Key ---------------------------------------------------------


@pytest.mark.parametrize("value", [None, ""])
def test_missing_key(value):
    assert code_of(validate_idempotency_key, value) == (400, "IDEMPOTENCY_REQUIRED")


@pytest.mark.parametrize("value", ["short7c", "x" * 129, "abc\x01defgh", "clé-unique-01"])
def test_malformed_key(value):
    assert code_of(validate_idempotency_key, value) == (400, "INVALID_REQUEST")


@pytest.mark.parametrize("value", ["abcdefgh", "x" * 128, "contract-1234 ok"])
def test_valid_key(value):
    assert validate_idempotency_key(value) == value


# --- JSON and structure ------------------------------------------------------


@pytest.mark.parametrize("raw", [b"{not json", b"", b"\xff\xfe"])
def test_invalid_json(raw):
    assert code_of(parse_order_request, raw) == (400, "INVALID_JSON")


@pytest.mark.parametrize(
    "raw",
    [
        b"[]",
        body(customer_id=""),
        body(customer_id="   "),
        body(customer_id="x" * 65),
        body(customer_id=42),
        body(items=[]),
        body(items={"sku": "KIT-100"}),
        body(items=[{"sku": "KIT-100", "quantity": 1}] * 11),
        body(items=["KIT-100"]),
        body(items=[{"quantity": 1}]),
        body(items=[{"sku": 100, "quantity": 1}]),
    ],
)
def test_invalid_structure(raw):
    assert code_of(parse_order_request, raw) == (400, "INVALID_REQUEST")


# --- Quantity ----------------------------------------------------------------


@pytest.mark.parametrize("qty", [0, 21, -1, True, False, 1.0, "1", None])
def test_invalid_quantity(qty):
    raw = body(items=[{"sku": "KIT-100", "quantity": qty}])
    assert code_of(parse_order_request, raw) == (422, "INVALID_QUANTITY")


def test_missing_quantity():
    raw = body(items=[{"sku": "KIT-100"}])
    assert code_of(parse_order_request, raw) == (422, "INVALID_QUANTITY")


def test_quantity_checked_before_sku():
    raw = body(items=[{"sku": "NOPE", "quantity": 0}])
    assert code_of(parse_order_request, raw) == (422, "INVALID_QUANTITY")


# --- SKU ---------------------------------------------------------------------


def test_unknown_sku():
    order = parse_order_request(body(items=[{"sku": "NOPE-1", "quantity": 1}]))
    assert code_of(check_known_skus, order, KNOWN) == (422, "INVALID_SKU")


def test_known_skus_pass():
    order = parse_order_request(body())
    check_known_skus(order, KNOWN)


# --- Aggregation and hashing -------------------------------------------------


def test_duplicate_lines_are_added_and_sorted():
    assert aggregate_lines([("PART-200", 1), ("KIT-100", 2), ("PART-200", 3)]) == {
        "KIT-100": 2,
        "PART-200": 4,
    }
    assert list(aggregate_lines([("PART-200", 1), ("KIT-100", 1)])) == ["KIT-100", "PART-200"]


def test_multiline_order_from_checker():
    raw = body(items=[{"sku": "PACK-300", "quantity": 2}, {"sku": "PACK-300", "quantity": 2}])
    assert parse_order_request(raw).lines == {"PACK-300": 4}


def test_hash_ignores_key_order():
    a = {"customer_id": "C1", "items": [{"sku": "KIT-100", "quantity": 1}]}
    b = {"items": [{"quantity": 1, "sku": "KIT-100"}], "customer_id": "C1"}
    assert canonical_hash(a) == canonical_hash(b)


def test_hash_detects_different_payload():
    a = {"customer_id": "C1", "items": [{"sku": "KIT-100", "quantity": 1}]}
    b = {"customer_id": "C2", "items": [{"sku": "KIT-100", "quantity": 1}]}
    assert canonical_hash(a) != canonical_hash(b)
