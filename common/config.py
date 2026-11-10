"""The only place where environment variables are read.

Every other module receives a Settings object instead of calling os.environ.
Names and defaults follow section 3 of docs/team-guide.md.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from urllib.parse import urlparse

QUEUE_BACKENDS = {"redis", "postgres"}


def _str(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _int(name: str, default: int) -> int:
    return int(_str(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(_str(name, str(default)))


def _bool(name: str, default: bool) -> bool:
    return _str(name, "true" if default else "false").lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # repr=False keeps the password out of logs and print() output.
    database_url: str = field(repr=False)
    redis_url: str = field(repr=False)
    queue_backend: str
    app_env: str
    api_port: int
    max_body_bytes: int
    log_level: str
    worker_id: str
    worker_max_attempts: int
    worker_lease_seconds: int
    worker_poll_interval_seconds: float
    worker_processing_delay_seconds: float
    worker_backoff_base_seconds: float
    worker_backoff_max_seconds: float
    worker_metrics_port: int
    poison_test_mode: bool

    @property
    def database_name(self) -> str:
        """Database name from the URL, used by the test-only reset guard."""
        return urlparse(self.database_url).path.lstrip("/")


def load_settings() -> Settings:
    """Read and validate configuration. Fails fast on a missing or invalid value."""
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    queue_backend = _str("QUEUE_BACKEND", "postgres").lower()
    if queue_backend not in QUEUE_BACKENDS:
        raise RuntimeError(f"QUEUE_BACKEND must be one of {sorted(QUEUE_BACKENDS)}")

    settings = Settings(
        database_url=database_url,
        redis_url=_str("REDIS_URL", "redis://redis:6379/0"),
        queue_backend=queue_backend,
        app_env=_str("APP_ENV", "test").lower(),
        api_port=_int("API_PORT", 8080),
        max_body_bytes=_int("MAX_BODY_BYTES", 16384),
        log_level=_str("LOG_LEVEL", "INFO").upper(),
        worker_id=_str("WORKER_ID", socket.gethostname()),
        worker_max_attempts=_int("WORKER_MAX_ATTEMPTS", 5),
        worker_lease_seconds=_int("WORKER_LEASE_SECONDS", 20),
        worker_poll_interval_seconds=_float("WORKER_POLL_INTERVAL_SECONDS", 2.0),
        worker_processing_delay_seconds=_float("WORKER_PROCESSING_DELAY_SECONDS", 0.5),
        worker_backoff_base_seconds=_float("WORKER_BACKOFF_BASE_SECONDS", 1.0),
        worker_backoff_max_seconds=_float("WORKER_BACKOFF_MAX_SECONDS", 30.0),
        worker_metrics_port=_int("WORKER_METRICS_PORT", 9100),
        poison_test_mode=_bool("POISON_TEST_MODE", False),
    )

    if settings.worker_max_attempts < 1:
        raise RuntimeError("WORKER_MAX_ATTEMPTS must be at least 1")
    if settings.max_body_bytes < 1:
        raise RuntimeError("MAX_BODY_BYTES must be positive")
    return settings
