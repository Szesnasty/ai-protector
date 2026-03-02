"""Health check router."""

import httpx
import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, get_settings
from src.db.session import get_db, get_redis
from src.schemas.health import HealthResponse, ServiceHealth

router = APIRouter(tags=["health"])
logger = structlog.get_logger()


async def _check_db(db: AsyncSession) -> ServiceHealth:
    try:
        await db.execute(text("SELECT 1"))
        return ServiceHealth(status="ok")
    except Exception as exc:
        logger.warning("health_db_error", error=str(exc))
        return ServiceHealth(status="error", detail=str(exc))


async def _check_redis() -> ServiceHealth:
    try:
        redis = await get_redis()
        pong = await redis.ping()
        if pong:
            return ServiceHealth(status="ok")
        return ServiceHealth(status="error", detail="no PONG")
    except Exception as exc:
        logger.warning("health_redis_error", error=str(exc))
        return ServiceHealth(status="error", detail=str(exc))


async def _check_ollama(base_url: str) -> ServiceHealth:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                return ServiceHealth(status="ok")
            return ServiceHealth(status="error", detail=f"HTTP {resp.status_code}")
    except Exception as exc:
        logger.warning("health_ollama_error", error=str(exc))
        return ServiceHealth(status="error", detail=str(exc))


async def _check_langfuse(host: str) -> ServiceHealth:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{host}/api/public/health")
            if resp.status_code == 200:
                return ServiceHealth(status="ok")
            return ServiceHealth(status="error", detail=f"HTTP {resp.status_code}")
    except Exception as exc:
        logger.warning("health_langfuse_error", error=str(exc))
        return ServiceHealth(status="error", detail=str(exc))


@router.get("/health", response_model=HealthResponse)
async def health(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> HealthResponse:
    """Check health of all dependent services."""
    services = {
        "db": await _check_db(db),
        "redis": await _check_redis(),
        "ollama": await _check_ollama(settings.ollama_base_url),
        "langfuse": await _check_langfuse(settings.langfuse_host),
    }

    overall = "ok" if all(s.status == "ok" for s in services.values()) else "degraded"

    return HealthResponse(
        status=overall,
        services=services,
        version=settings.app_version,
    )
