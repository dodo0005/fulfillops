"""Order routes. POST /api/v1/orders (create_order) is added in tasks A4-A5."""

from __future__ import annotations

from fastapi import APIRouter, Request

from api.errors import ApiError
from api.orders_service import fetch_order

router = APIRouter(prefix="/api/v1")


@router.get("/orders/{order_id}")
def get_order(order_id: str, request: Request) -> dict:
    order = fetch_order(request.app.state.pool, order_id)
    if order is None:
        raise ApiError(404, "ORDER_NOT_FOUND", "Order not found")
    return order
