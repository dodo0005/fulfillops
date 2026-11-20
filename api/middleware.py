"""Request-level guards and request metrics."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from api.errors import ApiError
from api.metrics import HTTP_LATENCY, HTTP_REQUESTS


async def limit_body_size(request: Request, max_bytes: int) -> bytes:
    """Step 1: read the body, but never more than max_bytes (+1 to detect overflow).

    A huge body is refused without being loaded fully into memory.
    """
    too_large = ApiError(413, "PAYLOAD_TOO_LARGE", "Request body exceeds 16 KiB")
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
        raise too_large
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > max_bytes:
            raise too_large
    return bytes(body)


def _route_template(request: Request) -> str:
    """'/api/v1/orders/{order_id}', never the real path: real IDs would create one
    time series per order (unbounded cardinality) and leak identifiers into metrics."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


async def request_metrics(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    status = 500  # if the handler crashes before responding, count it as a 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = _route_template(request)
        HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
        HTTP_LATENCY.labels(request.method, route).observe(time.perf_counter() - start)
