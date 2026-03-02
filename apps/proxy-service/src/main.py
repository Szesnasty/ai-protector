"""AI Protector Proxy Service — FastAPI application."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.db.seed import seed_policies
from src.db.session import close_db, close_redis, engine
from src.logging import CorrelationIdMiddleware, setup_logging
from src.models import Base
from src.routers.health import router as health_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    settings = get_settings()
    setup_logging(log_level=settings.log_level, json_logs=False)

    logger.info("proxy_starting", version=settings.app_version)

    # Ensure tables exist (dev convenience — production uses Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await seed_policies()
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
