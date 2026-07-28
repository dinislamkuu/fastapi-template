from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import router as api_v1_router
from app.cache.redis import create_redis_client
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import AccessLogMiddleware, configure_logging
from app.core.request_id import RequestIDMiddleware
from app.db.session import create_engine, create_sessionmaker
from app.health.router import router as health_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.db_engine = create_engine(settings)
    app.state.sessionmaker = create_sessionmaker(app.state.db_engine)
    app.state.redis_client = create_redis_client(settings)
    logger.info("application_started")
    try:
        yield
    finally:
        await app.state.redis_client.aclose()
        await app.state.db_engine.dispose()
        logger.info("application_stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(
        log_level=settings.log_level,
        service=settings.app_name,
        environment=settings.environment,
        version=settings.app_version,
    )
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)
    app.add_middleware(AccessLogMiddleware, logger=structlog.get_logger("access"))
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(api_v1_router)
    return app


app = create_app()
