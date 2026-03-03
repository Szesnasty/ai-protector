"""Pydantic schemas for Request log."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class RequestRead(BaseModel):
    """Lightweight schema for list view (excludes large JSONB fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: str
    policy_id: uuid.UUID
    policy_name: str = ""
    intent: str | None = None
    prompt_preview: str | None = None
    decision: str
    risk_flags: dict | None = None
    risk_score: float | None = None
    latency_ms: int | None = None
    model_used: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    blocked_reason: str | None = None
    response_masked: bool | None = None
    created_at: datetime


class RequestDetail(RequestRead):
    """Full detail schema — includes heavy JSONB columns."""

    prompt_hash: str | None = None
    scanner_results: dict | None = None
    output_filter_results: dict | None = None
    node_timings: dict | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic wrapper for paginated list responses."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
