from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Environment

router = APIRouter(tags=["version"])


class VersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: Literal["fastapi-production-template"]
    version: str = Field(min_length=1, max_length=50)
    environment: Environment
    build_sha: str | None = Field(default=None, max_length=80)


@router.get("/version", response_model=VersionResponse)
async def version(request: Request) -> VersionResponse:
    settings = request.app.state.settings
    return VersionResponse(
        service="fastapi-production-template",
        version=settings.app_version,
        environment=settings.environment,
        build_sha=settings.build_sha,
    )
