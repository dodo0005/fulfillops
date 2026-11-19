"""Recreate the isolated TEST dataset: no orders, seed stock 7 / 12 / 5.

Run with: python -m common.reset_test_data  (or scripts/reset-test-data.sh)
Refuses to run unless APP_ENV=test AND the database name contains "test".
"""

from __future__ import annotations

import sys

import psycopg

from common.config import Settings, load_settings
from common.logging import configure_logging, log_event

SEED_STOCK = {"KIT-100": 7, "PART-200": 12, "PACK-300": 5}  # same as 002_seed.sql


class NotATestEnvironment(RuntimeError):
    pass


def assert_test_environment(settings: Settings) -> None:
    if settings.app_env != "test" or "test" not in settings.database_name:
        raise NotATestEnvironment(
            "refusing to reset: APP_ENV must be 'test' and the database name must "
            f"contain 'test' (got APP_ENV={settings.app_env!r}, "
            f"database={settings.database_name!r})"
        )


def reset(conn: psycopg.Connection) -> None:
    with conn.transaction():
        conn.execute("TRUNCATE receipts, jobs, order_items, orders")
        for sku, available in SEED_STOCK.items():
            conn.execute(
                "UPDATE inventory SET available = %s, updated_at = now() WHERE sku = %s",
                (available, sku),
            )


def main() -> int:
    settings = load_settings()
    configure_logging("reset", settings.log_level)
    try:
        assert_test_environment(settings)
    except NotATestEnvironment as exc:
        log_event("reset_refused", level="error", reason=str(exc))
        return 2
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        reset(conn)
    log_event("reset_done", stock=SEED_STOCK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
