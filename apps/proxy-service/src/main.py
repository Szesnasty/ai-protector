"""AI Protector Proxy Service — FastAPI application."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.db.seed import seed_denylist, seed_policies
from src.db.session import close_db, close_redis, engine
from src.llm.exceptions import LLMError
from src.logging import CorrelationIdMiddleware, setup_logging
from src.models import Base
from src.routers.analytics import router as analytics_router
from src.routers.chat import router as chat_router
from src.routers.direct import router as chat_direct_router
from src.routers.health import router as health_router
from src.routers.models import router as models_router
from src.routers.policies import router as policies_router
from src.routers.requests import router as requests_router
from src.routers.rules import router as rules_router
from src.routers.scan import router as scan_router
from src.routers.scenarios import router as scenarios_router
from src.schemas.chat import ErrorDetail, ErrorResponse

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    settings = get_settings()
    setup_logging(log_level=settings.log_level, json_logs=settings.json_logs)

    # Silence verbose LiteLLM logs
    os.environ["LITELLM_LOG"] = settings.litellm_log_level

    logger.info("proxy_starting", version=settings.app_version)

    # Ensure tables exist (dev convenience — production uses Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await seed_policies()
    await seed_denylist()

    # Seed wizard data (reference agent, demo tools/roles)
    from src.wizard import seed_wizard

    await seed_wizard()

    # Cancel any benchmark runs orphaned by a previous crash / restart
    from src.db.session import async_session
    from src.red_team.persistence.repository import BenchmarkRunRepository

    async with async_session() as session:
        repo = BenchmarkRunRepository(session)
        cancelled = await repo.cancel_stale_runs()
        await session.commit()
        if cancelled:
            logger.info("stale_runs_cancelled", count=cancelled)

    # ── Cleanup expired auth secrets (24 h TTL) on startup ────────────
    from src.red_team.api.service import cleanup_expired_secrets

    async with async_session() as session:
        cleaned = await cleanup_expired_secrets(session)
        if cleaned:
            logger.info("expired_secrets_cleaned", count=cleaned)

    # ── Preload ML models in background (eliminates ~50 s cold-start) ──
    import asyncio

    async def _preload_scanners() -> None:
        """Warm up heavy ML singletons so the first request is fast."""
        try:
            if settings.enable_llm_guard:
                from src.pipeline.nodes.llm_guard import get_scanners

                logger.info("preload_start", scanner="llm_guard")
                await asyncio.to_thread(get_scanners, {})
            if settings.enable_nemo_guardrails:
                from src.pipeline.nodes.nemo_guardrails import get_rails

                logger.info("preload_start", scanner="nemo_guardrails")
                await asyncio.to_thread(get_rails)
            if settings.enable_presidio:
                from src.pipeline.nodes.presidio import get_analyzer, get_anonymizer

                logger.info("preload_start", scanner="presidio")
                await asyncio.to_thread(get_analyzer)
                await asyncio.to_thread(get_anonymizer)
            logger.info("preload_complete", msg="All ML models loaded")
        except Exception as exc:
            logger.error(
                "preload_failed",
                error_type=type(exc).__name__,
                msg="Non-fatal — models will lazy-load on first request",
            )

    asyncio.create_task(_preload_scanners())

    # ── Periodic cleanup of expired auth secrets (every 60 min) ────────
    async def _periodic_secret_cleanup() -> None:
        import asyncio as _aio

        while True:
            await _aio.sleep(3600)  # 60 minutes
            try:
                async with async_session() as sess:
                    cleaned = await cleanup_expired_secrets(sess)
                    if cleaned:
                        logger.info("periodic_secrets_cleaned", count=cleaned)
            except Exception:
                logger.warning("periodic_secret_cleanup_failed", exc_info=True)

    _cleanup_task = asyncio.create_task(_periodic_secret_cleanup())

    logger.info("proxy_ready")

    yield

    # Cancel periodic cleanup on shutdown
    _cleanup_task.cancel()

    # Shutdown
    await close_db()
    await close_redis()
    logger.info("proxy_stopped")


settings = get_settings()

app = FastAPI(
    title="AI Protector — Proxy Service",
    description="LLM Firewall with agentic security pipeline",
    version=settings.app_version,
    lifespan=lifespan,
)

# -- Middleware --
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "x-client-id",
        "x-policy",
        "x-api-key",
        "x-correlation-id",
    ],
    expose_headers=[
        "x-decision",
        "x-intent",
        "x-risk-score",
        "x-pipeline",
        "x-correlation-id",
    ],
)
app.add_middleware(CorrelationIdMiddleware)

# -- Routers --
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(chat_direct_router)
app.include_router(models_router)

# Agent Wizard — self-contained module (specs 26-33)
from src.wizard import wizard_router  # noqa: E402

app.include_router(wizard_router, prefix="/v1")

app.include_router(analytics_router, prefix="/v1")
app.include_router(policies_router, prefix="/v1")
app.include_router(requests_router, prefix="/v1")
app.include_router(rules_router, prefix="/v1")
app.include_router(scan_router)
app.include_router(scenarios_router, prefix="/v1")

# Red Team Benchmark
from src.red_team.api.routes import router as benchmark_router  # noqa: E402

app.include_router(benchmark_router, prefix="/v1")


# -- Exception handlers --
@app.exception_handler(LLMError)
async def llm_error_handler(_request: Request, exc: LLMError) -> JSONResponse:
    """Map LLM exceptions to OpenAI-compatible error responses."""
    body = ErrorResponse(
        error=ErrorDetail(
            message=exc.message,
            type=exc.error_type,
            code=str(exc.status_code),
        )
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())
