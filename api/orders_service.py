"""Order logic that talks to the database.

accept_order() is the heart of the project: idempotency and stock reservation in ONE
transaction, so either everything is saved or nothing is (see docs/ADR-001.md).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from api.errors import ApiError
from api.validation import OrderRequest
from common.logging import log_event


@dataclass(frozen=True)
class AcceptResult:
    order_id: str
    replayed: bool  # True when the same key + same payload was already accepted before


def _key_fingerprint(key: str) -> str:
    """Safe to log: first 8 hex chars of the key's hash, never the key itself."""
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def accept_order(
    pool: ConnectionPool, key: str, order: OrderRequest, max_attempts: int
) -> AcceptResult:
    order_id = uuid.uuid4()
    job_id = uuid.uuid4()

    with pool.connection() as conn, conn.transaction():
        # 1. Prices come from the database, never from the client.
        prices = dict(
            conn.execute(
                "SELECT sku, unit_price_cents FROM products WHERE sku = ANY(%s)",
                (list(order.lines),),
            ).fetchall()
        )
        if len(prices) != len(order.lines):
            raise ApiError(422, "INVALID_SKU", "Unknown SKU in order")
        total_cents = sum(prices[sku] * qty for sku, qty in order.lines.items())

        # 2. Claim the idempotency key. If another request with the same key is still
        #    running (on any API replica), this INSERT waits for it to commit or roll back.
        inserted = conn.execute(
            """
            INSERT INTO orders (order_id, idempotency_key, request_hash, customer_id,
                                status, total_cents)
            VALUES (%s, %s, %s, %s, 'queued', %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING order_id
            """,
            (order_id, key, order.request_hash, order.customer_id, total_cents),
        ).fetchone()

        if inserted is None:
            # The key already exists: same payload -> replay, different payload -> conflict.
            existing = conn.execute(
                "SELECT order_id::text, request_hash FROM orders WHERE idempotency_key = %s",
                (key,),
            ).fetchone()
            if existing[1] != order.request_hash:
                log_event("order_key_conflict", key_fp=_key_fingerprint(key))
                raise ApiError(
                    409, "IDEMPOTENCY_CONFLICT", "Idempotency-Key was used with another payload"
                )
            log_event("order_replayed", order_id=existing[0], key_fp=_key_fingerprint(key))
            return AcceptResult(order_id=existing[0], replayed=True)

        # 3. Reserve stock. Sorted SKU order (from aggregate_lines) = same lock order in
        #    every transaction = no deadlocks. "available >= qty" makes overselling impossible.
        for sku, qty in order.lines.items():
            updated = conn.execute(
                """
                UPDATE inventory SET available = available - %s, updated_at = now()
                WHERE sku = %s AND available >= %s
                """,
                (qty, sku, qty),
            )
            if updated.rowcount == 0:
                # Raising inside the transaction rolls back the order row too.
                raise ApiError(409, "OUT_OF_STOCK", "Not enough items available")

        # 4. Lines and the job for the worker, still in the same transaction.
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO order_items (order_id, sku, quantity, unit_price_cents)
                VALUES (%s, %s, %s, %s)
                """,
                [(order_id, sku, qty, prices[sku]) for sku, qty in order.lines.items()],
            )
        conn.execute(
            """
            INSERT INTO jobs (job_id, order_id, status, max_attempts, next_attempt_at)
            VALUES (%s, %s, 'queued', %s, now())
            """,
            (job_id, order_id, max_attempts),
        )
    # Leaving the "with" block committed everything. Only now may the API answer 202.
    log_event(
        "order_accepted",
        order_id=str(order_id),
        key_fp=_key_fingerprint(key),
        lines=len(order.lines),
    )
    return AcceptResult(order_id=str(order_id), replayed=False)


def fetch_known_skus(pool: ConnectionPool) -> set[str]:
    with pool.connection() as conn:
        return {row[0] for row in conn.execute("SELECT sku FROM products").fetchall()}


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
