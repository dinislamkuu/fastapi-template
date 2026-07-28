from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

os.environ["APP_NAME"] = "fastapi-production-template"
os.environ["APP_VERSION"] = "0.1.0"
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://app_test:app_test_password@127.0.0.1:55432/app_test"
)
os.environ["REDIS_URL"] = "redis://127.0.0.1:56379/1"
os.environ["DB_POOL_SIZE"] = "2"
os.environ["DB_MAX_OVERFLOW"] = "2"
os.environ["READINESS_TIMEOUT_SECONDS"] = "1"
os.environ["DOCS_ENABLED"] = "true"
os.environ["ALLOWED_HOSTS"] = "testserver,localhost,127.0.0.1"

from app.core.config import reset_settings_cache  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_settings() -> Iterator[None]:
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture
async def app_client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client


@pytest.fixture
def alembic_config() -> Config:
    return Config("alembic.ini")


@pytest.fixture(scope="session")
def migrated_database() -> None:
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return


@pytest.fixture
async def clean_redis() -> AsyncIterator[None]:
    client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await client.flushdb()
    await client.aclose()
    yield
    client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await client.flushdb()
    await client.aclose()


@pytest.fixture
async def app_with_lifespan() -> AsyncIterator[object]:
    app = create_app()
    async with app.router.lifespan_context(app):
        yield app
        engine = getattr(app.state, "db_engine", None)
        redis_client = getattr(app.state, "redis_client", None)
        if isinstance(redis_client, Redis):
            await redis_client.aclose()
        if isinstance(engine, AsyncEngine):
            await engine.dispose()
