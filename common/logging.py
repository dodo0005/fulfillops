"""Structured JSON logging: one JSON object per line on stdout.

Never pass secrets, raw idempotency keys, customer IDs or request bodies as fields
(see section 6 of docs/team-guide.md).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

_logger = logging.getLogger("fulfillops")
_service = "unknown"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "service": _service,
            "event": record.getMessage(),
        }
        payload.update(getattr(record, "fields", {}))
        return json.dumps(payload, default=str)


def configure_logging(service: str, level: str = "INFO") -> None:
    """Call once at process start, with service = "api" or "worker"."""
    global _service
    _service = service
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    _logger.handlers = [handler]
    _logger.setLevel(level.upper())
    _logger.propagate = False


def log_event(event: str, level: str = "info", **fields: object) -> None:
    """Log one named event, e.g. log_event("order_accepted", order_id=oid)."""
    _logger.log(getattr(logging, level.upper(), logging.INFO), event, extra={"fields": fields})
