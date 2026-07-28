from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.version import router as version_router

router = APIRouter(prefix="/api/v1")
router.include_router(version_router)
