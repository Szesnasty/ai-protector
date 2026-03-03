"""Health check router."""

import os
import time

import httpx
import psutil
import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, get_settings
from src.db.session import get_db, get_redis
from src.schemas.health import HealthResponse, ServiceHealth, SystemMetrics

_PROCESS_START = time.monotonic()

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


async def _collect_metrics(db: AsyncSession) -> SystemMetrics:
    """Collect system resource metrics."""
    # Memory
    mem = psutil.virtual_memory()
    # CPU (non-blocking — returns instant snapshot)
    cpu = psutil.cpu_percent(interval=None)
    # Disk
    disk = psutil.disk_usage("/")
    # Process info
    proc = psutil.Process(os.getpid())
    # Total requests from DB
    try:
        from src.models.request import Request
        result = await db.execute(select(func.count()).select_from(Request))
        total_requests = result.scalar() or 0
    except Exception:
        total_requests = 0

    return SystemMetrics(
        memory_used_mb=round(mem.used / 1024 / 1024, 1),
        memory_total_mb=round(mem.total / 1024 / 1024, 1),
        memory_percent=round(mem.percent, 1),
        cpu_percent=round(cpu, 1),
        disk_used_gb=round(disk.used / 1024 / 1024 / 1024, 1),
        disk_total_gb=round(disk.total / 1024 / 1024 / 1024, 1),
        disk_percent=round(disk.percent, 1),
        uptime_seconds=round(time.monotonic() - _PROCESS_START, 0),
        pid=os.getpid(),
        open_files=len(proc.open_files()),
        threads=proc.num_threads(),
        total_requests=total_requests,
    )


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

    try:
        metrics = await _collect_metrics(db)
    except Exception as exc:
        logger.warning("health_metrics_error", error=str(exc))
        metrics = None

    return HealthResponse(
        status=overall,
        services=services,
        version=settings.app_version,
        metrics=metrics,
    )
