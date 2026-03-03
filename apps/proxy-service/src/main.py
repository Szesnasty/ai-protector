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
from src.routers.chat import router as chat_router
from src.routers.health import router as health_router
from src.routers.policies import router as policies_router
from src.routers.requests import router as requests_router
from src.routers.rules import router as rules_router
from src.schemas.chat import ErrorDetail, ErrorResponse

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    settings = get_settings()
    setup_logging(log_level=settings.log_level, json_logs=False)

    # Silence verbose LiteLLM logs
    os.environ["LITELLM_LOG"] = settings.litellm_log_level

    logger.info("proxy_starting", version=settings.app_version)

    # Ensure tables exist (dev convenience — production uses Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await seed_policies()
    await seed_denylist()
    logger.info("proxy_ready")

    yield

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
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationIdMiddleware)

# -- Routers --
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(policies_router, prefix="/v1")
app.include_router(requests_router, prefix="/v1")
app.include_router(rules_router, prefix="/v1")


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
