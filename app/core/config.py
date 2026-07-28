from __future__ import annotations

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def package_version() -> str:
    try:
        return version("fastapi-production-template")
    except PackageNotFoundError:
        return "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    app_name: str = Field(default="fastapi-production-template", alias="APP_NAME")
    app_version: str = Field(default_factory=package_version, alias="APP_VERSION")
    environment: Environment = Field(default="development", alias="ENVIRONMENT")
    log_level: LogLevel = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    db_pool_size: int = Field(default=5, ge=1, le=50, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, ge=0, le=100, alias="DB_MAX_OVERFLOW")
    readiness_timeout_seconds: float = Field(
        default=1.5,
        gt=0,
        le=10,
        alias="READINESS_TIMEOUT_SECONDS",
    )
    docs_enabled: bool = Field(default=True, alias="DOCS_ENABLED")
    allowed_hosts: str = Field(default="localhost,127.0.0.1", alias="ALLOWED_HOSTS")
    build_sha: str | None = Field(default=None, alias="BUILD_SHA")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            msg = "DATABASE_URL must use postgresql+asyncpg://"
            raise ValueError(msg)
        return value

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        if not value.startswith(("redis://", "rediss://")):
            msg = "REDIS_URL must use redis:// or rediss://"
            raise ValueError(msg)
        return value

    @field_validator("build_sha", mode="before")
    @classmethod
    def empty_build_sha_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    @model_validator(mode="after")
    def validate_production_safety(self) -> Settings:
        if self.environment != "production":
            return self

        unsafe_values = {
            "example",
            "placeholder",
            "changeme",
            "change-me",
            "password",
        }
        combined_url_parts = {
            part.strip().lower()
            for url in (self.database_url, self.redis_url)
            for part in url.replace("/", ":").replace("@", ":").split(":")
        }
        if unsafe_values & combined_url_parts:
            msg = "production configuration contains placeholder values"
            raise ValueError(msg)
        if "*" in self.allowed_hosts_list or not self.allowed_hosts_list:
            msg = "production ALLOWED_HOSTS must be explicit"
            raise ValueError(msg)
        if self.docs_enabled:
            msg = "production DOCS_ENABLED must be false"
            raise ValueError(msg)
        return self

    def runtime_configuration_ok(self) -> bool:
        return bool(self.database_url and self.redis_url and self.allowed_hosts_list)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
