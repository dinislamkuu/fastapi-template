from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, Query
from fastapi import HTTPException as FastAPIHTTPException
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.errors import register_error_handlers
from app.core.request_id import REQUEST_ID_HEADER, RequestIDMiddleware


@pytest.mark.asyncio
async def test_live_returns_ok_without_dependency_checks(app_client: AsyncClient) -> None:
    response = await app_client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_version_schema(app_client: AsyncClient) -> None:
    response = await app_client.get("/api/v1/version")

    assert response.status_code == 200
    assert response.json() == {
        "service": "fastapi-production-template",
        "version": "0.1.0",
        "environment": "test",
        "build_sha": None,
    }


@pytest.mark.asyncio
async def test_request_id_is_generated(app_client: AsyncClient) -> None:
    response = await app_client.get("/health/live")

    assert response.headers[REQUEST_ID_HEADER]


@pytest.mark.asyncio
async def test_valid_request_id_is_preserved(app_client: AsyncClient) -> None:
    response = await app_client.get("/health/live", headers={REQUEST_ID_HEADER: "req-123.OK"})

    assert response.headers[REQUEST_ID_HEADER] == "req-123.OK"


@pytest.mark.asyncio
async def test_invalid_request_id_is_replaced(app_client: AsyncClient) -> None:
    response = await app_client.get("/health/live", headers={REQUEST_ID_HEADER: "bad\nvalue"})

    assert response.headers[REQUEST_ID_HEADER] != "bad\nvalue"
    assert len(response.headers[REQUEST_ID_HEADER]) <= 64


@pytest.mark.asyncio
async def test_unhandled_error_does_not_leak_exception() -> None:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("sensitive stack details")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/boom", headers={REQUEST_ID_HEADER: "probe-fixed-id"})

    body = response.json()
    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "probe-fixed-id"
    assert body["error"]["message"] == "Internal server error"
    assert body["error"]["request_id"] == "probe-fixed-id"
    assert "sensitive" not in response.text


@pytest.mark.asyncio
async def test_404_uses_single_error_format(app_client: AsyncClient) -> None:
    response = await app_client.get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"
    assert response.headers[REQUEST_ID_HEADER]


@pytest.mark.asyncio
async def test_http_exception_with_structured_detail_keeps_status() -> None:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)

    @app.get("/conflict")
    async def conflict() -> dict[str, str]:
        raise FastAPIHTTPException(status_code=409, detail={"reason": "conflict"})

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/conflict")

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Conflict"


@pytest.mark.asyncio
async def test_validation_errors_use_single_format() -> None:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)

    @app.get("/needs-int")
    async def needs_int(value: int = Query(...)) -> dict[str, int]:
        return {"value": value}

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/needs-int", params={"value": "nope"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_readiness_503_when_dependency_fails(app_with_lifespan: Any) -> None:
    app_with_lifespan.state.db_engine = create_async_engine(
        "postgresql+asyncpg://bad:bad@127.0.0.1:1/bad",
        connect_args={"timeout": 0.1},
    )
    transport = ASGITransport(app=app_with_lifespan, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["checks"]["postgres"] == "error"
    assert "bad@" not in response.text
    assert "ConnectionRefusedError" not in response.text
    await app_with_lifespan.state.db_engine.dispose()


@pytest.mark.asyncio
async def test_readiness_503_when_redis_fails(app_with_lifespan: Any) -> None:
    redis_client = Redis.from_url(
        "redis://127.0.0.1:1/0",
        socket_connect_timeout=0.1,
        socket_timeout=0.1,
        decode_responses=True,
    )
    app_with_lifespan.state.redis_client = redis_client
    transport = ASGITransport(app=app_with_lifespan, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["checks"]["redis"] == "error"
    assert "Connection" not in response.text
    await redis_client.aclose()
