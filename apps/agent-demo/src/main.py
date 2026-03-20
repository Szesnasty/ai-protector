"""AI Protector Agent Demo — Customer Support Copilot."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.routers.chat import router as chat_router
from src.routers.health import router as health_router
from src.routers.traces import router as traces_router

logger = structlog.get_logger()

_AGENT_NAME = "Agent Demo"
_AGENT_PAYLOAD = {
    "name": _AGENT_NAME,
    "description": "Customer Support Copilot — full LangGraph agent with pre/post tool gates.",
    "team": "demo",
    "framework": "langgraph",
    "environment": "production",
    "is_public_facing": True,
    "has_tools": True,
    "has_write_actions": False,
    "touches_pii": False,
    "handles_secrets": False,
    "calls_external_apis": False,
}


async def _ensure_agent_registered(settings) -> None:
    """Register agent-demo with proxy-service wizard if no agent_id is set.

    Tries to find an existing agent by name first; creates one if not found.
    Updates settings.agent_id in-place so memory_node picks it up immediately.
    """
    if settings.agent_id:
        logger.info("agent_id_already_set", agent_id=settings.agent_id)
        return

    # proxy_base_url is like http://proxy-service:8000/v1 — strip /v1 for wizard API
    base = settings.proxy_base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    wizard_base = base + "/v1"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Search for existing agent by name
            resp = await client.get(
                f"{wizard_base}/agents",
                params={"search": _AGENT_NAME, "per_page": 5},
            )
            if resp.status_code == 200:
                for item in resp.json().get("items", []):
                    if item.get("name") == _AGENT_NAME:
                        settings.agent_id = item["id"]
                        logger.info(
                            "agent_demo_found_in_wizard",
                            agent_id=settings.agent_id,
                        )
                        return

            # 2. Not found — register
            resp = await client.post(f"{wizard_base}/agents", json=_AGENT_PAYLOAD)
            if resp.status_code == 201:
                settings.agent_id = resp.json()["id"]
                logger.info(
                    "agent_demo_registered",
                    agent_id=settings.agent_id,
                )
            elif resp.status_code == 409:
                # Race condition — search again
                resp2 = await client.get(
                    f"{wizard_base}/agents",
                    params={"search": _AGENT_NAME, "per_page": 5},
                )
                if resp2.status_code == 200:
                    for item in resp2.json().get("items", []):
                        if item.get("name") == _AGENT_NAME:
                            settings.agent_id = item["id"]
                            logger.info(
                                "agent_demo_registered_race",
                                agent_id=settings.agent_id,
                            )
                            return
            else:
                logger.warning(
                    "agent_demo_registration_failed",
                    status=resp.status_code,
                    body=resp.text[:300],
                )
    except Exception as exc:
        logger.warning("agent_demo_registration_error", error=str(exc)[:300])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    settings = get_settings()

    # Silence verbose LiteLLM logs
    os.environ["LITELLM_LOG"] = settings.litellm_log_level

    logger.info("agent_demo_starting", version=settings.app_version)

    # Auto-register with proxy-service wizard so traces are forwarded
    await _ensure_agent_registered(settings)

    logger.info(
        "agent_demo_ready",
        proxy_url=settings.proxy_base_url,
        model=settings.default_model,
        agent_id=settings.agent_id or "unregistered",
    )
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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "x-client-id", "x-api-key", "x-correlation-id"],
)

# Routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(traces_router)
