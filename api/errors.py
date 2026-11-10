"""One error format for every failure: {"error": {"code": "...", "message": "..."}}.

Messages are short and safe: no stack traces, SQL, connection strings or personal data.
"""

from __future__ import annotations

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

from common.logging import log_event


class ApiError(Exception):
    """Raise this anywhere in a route to return a contract error."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return error_response(404, "NOT_FOUND", "Route not found")
        if exc.status_code == 405:
            return error_response(405, "METHOD_NOT_ALLOWED", "Method not allowed")
        return error_response(exc.status_code, "HTTP_ERROR", "Request could not be processed")

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
        return error_response(400, "INVALID_REQUEST", "Request is malformed")

    @app.exception_handler(PoolTimeout)
    @app.exception_handler(psycopg.OperationalError)
    async def _db_unavailable(request: Request, exc: Exception) -> JSONResponse:
        log_event(
            "db_unavailable", level="error", route=request.url.path, error_type=type(exc).__name__
        )
        return error_response(503, "SERVICE_UNAVAILABLE", "Service temporarily unavailable")

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Only the exception type is logged; never the message (it could contain data).
        log_event(
            "unhandled_error", level="error", route=request.url.path, error_type=type(exc).__name__
        )
        return error_response(500, "INTERNAL_ERROR", "Internal server error")
