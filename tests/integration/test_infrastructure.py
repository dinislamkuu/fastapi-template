from __future__ import annotations

from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base import Base


@pytest.mark.asyncio
async def test_alembic_initial_migration_creates_metadata_table(
    migrated_database: None,
    app_with_lifespan: Any,
) -> None:
    engine: AsyncEngine = app_with_lifespan.state.db_engine

    async with engine.connect() as connection:
        tables = await connection.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

    assert "service_metadata" in tables


@pytest.mark.asyncio
async def test_alembic_metadata_has_no_drift(
    migrated_database: None,
    app_with_lifespan: Any,
) -> None:
    engine: AsyncEngine = app_with_lifespan.state.db_engine

    async with engine.connect() as connection:
        drift = await connection.run_sync(
            lambda sync_conn: compare_metadata(
                MigrationContext.configure(sync_conn),
                Base.metadata,
            )
        )

    assert drift == []


@pytest.mark.asyncio
async def test_postgres_select_one(migrated_database: None, app_with_lifespan: Any) -> None:
    engine: AsyncEngine = app_with_lifespan.state.db_engine

    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))

    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_redis_ping(clean_redis: None, app_with_lifespan: Any) -> None:
    redis_client: Redis = app_with_lifespan.state.redis_client

    assert await redis_client.ping() is True


@pytest.mark.asyncio
async def test_ready_returns_200_with_available_dependencies(
    migrated_database: None,
    clean_redis: None,
    app_with_lifespan: Any,
) -> None:
    transport = ASGITransport(app=app_with_lifespan, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"] == {
        "postgres": "ok",
        "redis": "ok",
        "configuration": "ok",
    }


@pytest.mark.asyncio
async def test_lifespan_closes_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    class FakeRedis:
        closed = False

        async def aclose(self) -> None:
            self.closed = True

    class FakeEngine:
        disposed = False

        async def dispose(self) -> None:
            self.disposed = True

    fake_redis = FakeRedis()
    fake_engine = FakeEngine()

    monkeypatch.setattr(main_module, "create_redis_client", lambda _settings: fake_redis)
    monkeypatch.setattr(main_module, "create_engine", lambda _settings: fake_engine)
    monkeypatch.setattr(main_module, "create_sessionmaker", lambda _engine: object())

    app = main_module.create_app()
    async with app.router.lifespan_context(app):
        pass

    assert fake_redis.closed is True
    assert fake_engine.disposed is True
