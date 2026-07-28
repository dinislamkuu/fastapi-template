from __future__ import annotations

import asyncio
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings

logger = structlog.get_logger(__name__)


async def check_postgres(engine: AsyncEngine, deadline_seconds: float) -> bool:
    async def _check() -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    try:
        async with asyncio.timeout(deadline_seconds):
            await _check()
    except Exception:
        logger.warning("readiness_postgres_failed", exc_info=True)
        return False
    return True


async def check_redis(client: Redis, deadline_seconds: float) -> bool:
    try:
        async with asyncio.timeout(deadline_seconds):
            result = await client.ping()
    except Exception:
        logger.warning("readiness_redis_failed", exc_info=True)
        return False
    return bool(result)


async def get_readiness(
    settings: Settings, engine: AsyncEngine, redis_client: Redis
) -> dict[str, str]:
    postgres_result, redis_result = await asyncio.gather(
        check_postgres(engine, settings.readiness_timeout_seconds),
        check_redis(redis_client, settings.readiness_timeout_seconds),
        return_exceptions=False,
    )
    return {
        "postgres": "ok" if postgres_result else "error",
        "redis": "ok" if redis_result else "error",
        "configuration": "ok" if settings.runtime_configuration_ok() else "error",
    }


def state_resource(state: Any, name: str) -> Any:
    return getattr(state, name)
