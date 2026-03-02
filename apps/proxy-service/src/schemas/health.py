"""Pydantic schemas for health endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class ServiceHealth(BaseModel):
    """Health status of a single service."""

    status: str  # "ok" | "error"
    detail: str | None = None


class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: str  # "ok" | "degraded"
    services: dict[str, ServiceHealth]
    version: str
