"""Apply db/migrations/*.sql in order, each exactly once.

Run with: python -m common.migrate
A Postgres advisory lock makes it safe when two API pods start at the same time.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import psycopg

from common.config import load_settings
from common.logging import configure_logging, log_event

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "db" / "migrations"
ADVISORY_LOCK_ID = 424242  # any constant number shared by every migrate process

_CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def latest_version() -> str:
    """Version name of the newest migration file, e.g. "002_seed"."""
    files = migration_files()
    if not files:
        raise RuntimeError(f"no migrations found in {MIGRATIONS_DIR}")
    return files[-1].stem


def run_migrations(conn: psycopg.Connection) -> list[str]:
    """Apply every migration not yet recorded. Returns the versions applied now.

    `conn` must be in autocommit mode so each `conn.transaction()` is a real transaction.
    """
    applied: list[str] = []
    conn.execute("SELECT pg_advisory_lock(%s)", (ADVISORY_LOCK_ID,))
    try:
        conn.execute(_CREATE_TRACKING_TABLE)
        for path in migration_files():
            version = path.stem
            with conn.transaction():  # the file and its record commit together, or not at all
                done = conn.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = %s", (version,)
                ).fetchone()
                if done:
                    continue
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            applied.append(version)
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_ID,))
    return applied


def _connect_with_retry(url: str, attempts: int = 30) -> psycopg.Connection:
    """The database may still be starting (Compose, Kubernetes initContainer)."""
    for attempt in range(1, attempts + 1):
        try:
            return psycopg.connect(url, autocommit=True, connect_timeout=3)
        except psycopg.OperationalError as exc:
            reason = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
            log_event("migrate_waiting_for_db", level="warning", attempt=attempt, error=reason)
            time.sleep(2)
    raise RuntimeError("database not reachable, giving up")


def main() -> int:
    settings = load_settings()
    configure_logging("migrate", settings.log_level)
    with _connect_with_retry(settings.database_url) as conn:
        applied = run_migrations(conn)
    log_event("migrations_done", applied=applied, latest=latest_version())
    return 0


if __name__ == "__main__":
    sys.exit(main())
