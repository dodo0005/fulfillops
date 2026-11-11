"""Order routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from api.errors import ApiError
from api.middleware import limit_body_size
from api.orders_service import fetch_known_skus, fetch_order
from api.validation import check_known_skus, parse_order_request, validate_idempotency_key

router = APIRouter(prefix="/api/v1")


@router.post("/orders", status_code=202)
async def create_order(request: Request) -> dict:
    settings = request.app.state.settings
    pool = request.app.state.pool

    raw = await limit_body_size(request, settings.max_body_bytes)  # step 1
    key = validate_idempotency_key(request.headers.get("Idempotency-Key"))  # step 2
    order = parse_order_request(raw)  # steps 3-5
    known = await run_in_threadpool(fetch_known_skus, pool)
    check_known_skus(order, known)  # step 6

    # Task A5 replaces this line with the atomic reservation (accept_order).
    del key
    raise ApiError(501, "NOT_IMPLEMENTED", "Order creation is not implemented yet")


@router.get("/orders/{order_id}")
def get_order(order_id: str, request: Request) -> dict:
    order = fetch_order(request.app.state.pool, order_id)
    if order is None:
        raise ApiError(404, "ORDER_NOT_FOUND", "Order not found")
    return order
