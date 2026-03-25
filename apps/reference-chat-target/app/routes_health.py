"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        service="reference-chat-target",
        mode=settings.app_mode,
        model=settings.gemini_model,
        streaming_enabled=settings.enable_streaming,
        retrieval_enabled=settings.enable_retrieval,
        tools_enabled=settings.enable_tools,
        structured_output_enabled=settings.enable_structured_output,
        canary_enabled=settings.enable_canary,
    )
