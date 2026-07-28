from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CheckStatus = Literal["ok", "error"]


class LiveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]


class ReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"]
    checks: dict[str, CheckStatus]
    request_id: str | None = Field(default=None, max_length=64)
