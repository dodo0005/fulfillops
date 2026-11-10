"""Order logic that talks to the database. accept_order() is added in task A5."""

from __future__ import annotations

import uuid

from psycopg_pool import ConnectionPool


def fetch_order(pool: ConnectionPool, order_id: str) -> dict | None:
    """Return {"order_id", "status", "total_cents"} or None if unknown.

    IDs that are not valid UUIDs are simply unknown (404), never a database error.
    """
    try:
        parsed = uuid.UUID(order_id)
    except ValueError:
        return None
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT order_id::text, status, total_cents FROM orders WHERE order_id = %s",
            (parsed,),
        ).fetchone()
    if row is None:
        return None
    return {"order_id": row[0], "status": row[1], "total_cents": row[2]}
