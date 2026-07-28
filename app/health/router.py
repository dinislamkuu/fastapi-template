from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.core.request_id import get_request_id
from app.health.schemas import LiveResponse, ReadyResponse
from app.health.service import get_readiness, state_resource

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadyResponse}},
)
async def ready(request: Request, response: Response) -> ReadyResponse:
    settings = state_resource(request.app.state, "settings")
    checks = await get_readiness(
        settings=settings,
        engine=state_resource(request.app.state, "db_engine"),
        redis_client=state_resource(request.app.state, "redis_client"),
    )
    is_ready = all(value == "ok" for value in checks.values())
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(
        status="ready" if is_ready else "not_ready",
        checks=checks,
        request_id=None if is_ready else get_request_id(),
    )
