"""FastAPI application. Start with: uvicorn api.main:app --host 0.0.0.0 --port 8080"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.errors import install_error_handlers
from api.routes_catalog import router as catalog_router
from api.routes_health import router as health_router
from api.routes_orders import router as orders_router
from common.config import load_settings
from common.db import create_pool
from common.logging import configure_logging, log_event


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging("api", settings.log_level)
    pool = create_pool(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool.open(wait=False)  # do not block startup if the database is down
        log_event("api_started", port=settings.api_port, queue_backend=settings.queue_backend)
        yield
        pool.close()
        log_event("api_stopped")

    # Interactive docs are switched off: smaller attack surface (see threat model).
    app = FastAPI(
        title="FulfillOps",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.pool = pool
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(catalog_router)
    app.include_router(orders_router)
    return app


app = create_app()
