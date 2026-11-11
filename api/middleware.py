"""Request-level guards. request_metrics is added in task A12."""

from __future__ import annotations

from fastapi import Request

from api.errors import ApiError


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
