"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.chat_service import ChatService
from app.config import Settings, load_settings
from app.gemini_client import create_backend
from app.retrieval import load_kb
from app.routes_chat import router as chat_router
from app.routes_health import router as health_router
from app.storage import create_stores

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings

    load_kb()
    logger.info("Knowledge base loaded")

    backend = create_backend(settings)
    conversations, traces = create_stores(settings)

    app.state.conversations = conversations
    app.state.traces = traces
    app.state.chat_service = ChatService(settings, backend, conversations, traces)

    logger.info(
        "reference-chat-target started — mode=%s model=%s",
        settings.app_mode,
        settings.gemini_model,
    )
    yield
    logger.info("reference-chat-target shutting down")


app = FastAPI(
    title="Reference Chat Target",
    description="Realistic benchmark target for AI Protector security testing.",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Auth middleware ──

_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    settings: Settings = request.app.state.settings
    if not settings.static_auth_token:
        return await call_next(request)

    if request.url.path in _PUBLIC_PATHS:
        return await call_next(request)

    auth_header = request.headers.get("authorization", "")
    expected = f"Bearer {settings.static_auth_token}"
    if auth_header != expected:
        return JSONResponse(
            status_code=401,
            content={
                "error": "Unauthorized",
                "detail": "Invalid or missing Bearer token.",
            },
        )
    return await call_next(request)


app.include_router(chat_router)
app.include_router(health_router)
