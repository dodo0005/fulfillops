"""Liveness and readiness, exactly as in API_CONTRACT_EN.md."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from common.db import check_ready

router = APIRouter()


@router.get("/health/live")
def live() -> dict[str, str]:
    """200 while the process is alive. Never touches the database."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready(request: Request) -> JSONResponse:
    """200 when orders can be accepted safely, 503 otherwise."""
    if check_ready(request.app.state.pool):
        return JSONResponse(status_code=200, content={"status": "ready"})
    return JSONResponse(status_code=503, content={"status": "not_ready"})
