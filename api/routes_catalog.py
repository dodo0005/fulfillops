"""GET /api/v1/catalog and GET /api/v1/inventory/{sku}."""

from __future__ import annotations

from fastapi import APIRouter, Request

from api.errors import ApiError

router = APIRouter(prefix="/api/v1")


@router.get("/catalog")
def get_catalog(request: Request) -> dict:
    with request.app.state.pool.connection() as conn:
        rows = conn.execute("SELECT sku, unit_price_cents FROM products ORDER BY sku").fetchall()
    return {"products": [{"sku": sku, "unit_price_cents": price} for sku, price in rows]}


@router.get("/inventory/{sku}")
def get_inventory(sku: str, request: Request) -> dict:
    with request.app.state.pool.connection() as conn:
        row = conn.execute("SELECT sku, available FROM inventory WHERE sku = %s", (sku,)).fetchone()
    if row is None:
        raise ApiError(404, "SKU_NOT_FOUND", "Unknown SKU")
    return {"sku": row[0], "available": row[1]}
