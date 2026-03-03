"""GET /health — readiness check."""

from __future__ import annotations

from fastapi import APIRouter

from src.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "version": settings.app_version}
