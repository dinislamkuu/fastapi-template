from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_required_settings_are_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(ValidationError, match="Field required"):
        Settings(_env_file=None)


def test_production_rejects_wildcard_hosts() -> None:
    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        Settings(
            APP_NAME="fastapi-production-template",
            ENVIRONMENT="production",
            LOG_LEVEL="INFO",
            DATABASE_URL="postgresql+asyncpg://user:strong-password@db.internal:5432/app",
            REDIS_URL="redis://redis.internal:6379/0",
            DOCS_ENABLED=False,
            ALLOWED_HOSTS="*",
        )


def test_production_rejects_enabled_docs() -> None:
    with pytest.raises(ValidationError, match="DOCS_ENABLED"):
        Settings(
            APP_NAME="fastapi-production-template",
            ENVIRONMENT="production",
            LOG_LEVEL="INFO",
            DATABASE_URL="postgresql+asyncpg://user:strong-password@db.internal:5432/app",
            REDIS_URL="redis://redis.internal:6379/0",
            DOCS_ENABLED=True,
            ALLOWED_HOSTS="api.internal",
        )
