"""Connection pool and the readiness check."""

from __future__ import annotations

from psycopg_pool import ConnectionPool

from common.config import Settings
from common.migrate import latest_version


def create_pool(settings: Settings, min_size: int = 1, max_size: int = 10) -> ConnectionPool:
    """Created closed; the app opens it at startup without waiting for the database.

    That way the process (and /health/live) comes up even if Postgres is down.
    """
    return ConnectionPool(
        settings.database_url,
        min_size=min_size,
        max_size=max_size,
        open=False,
        kwargs={"connect_timeout": 3},
    )


def check_ready(pool: ConnectionPool) -> bool:
    """True only if the database answers and the newest migration has been applied."""
    try:
        with pool.connection(timeout=2) as conn:
            row = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version = %s", (latest_version(),)
            ).fetchone()
            return row is not None
    except Exception:  # any DB problem means "not ready", never a crash
        return False
