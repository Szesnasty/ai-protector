"""Pydantic schemas for Request log."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RequestRead(BaseModel):
    """Schema for reading a request log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: str
    policy_id: uuid.UUID
    intent: str | None = None
    prompt_hash: str | None = None
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
