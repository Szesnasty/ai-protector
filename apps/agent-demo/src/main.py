"""AI Protector Agent Demo — Customer Support Copilot."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.routers.chat import router as chat_router
from src.routers.health import router as health_router
from src.routers.traces import router as traces_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    settings = get_settings()

    # Silence verbose LiteLLM logs
    os.environ["LITELLM_LOG"] = settings.litellm_log_level

    logger.info("agent_demo_starting", version=settings.app_version)
    logger.info("agent_demo_ready", proxy_url=settings.proxy_base_url, model=settings.default_model)
    yield
    logger.info("agent_demo_stopped")


settings = get_settings()

app = FastAPI(
    title="AI Protector — Agent Demo",
    description="Customer Support Copilot — demo agent behind the AI Protector firewall",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(traces_router)
