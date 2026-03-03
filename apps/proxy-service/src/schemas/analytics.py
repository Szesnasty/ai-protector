"""Pydantic schemas for analytics aggregation endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    """KPI summary for the dashboard header."""

    total_requests: int
    blocked: int
    modified: int
    allowed: int
    block_rate: float
    avg_risk: float
    avg_latency_ms: float
    top_intent: str | None


class TimelineBucket(BaseModel):
    """One time bucket in the timeline chart."""

    time: datetime
    total: int
    blocked: int
    modified: int
    allowed: int


class PolicyStats(BaseModel):
    """Per-policy aggregation."""

    policy_id: uuid.UUID
    policy_name: str
    total: int
    blocked: int
    modified: int
    allowed: int
    block_rate: float
    avg_risk: float


class RiskFlagCount(BaseModel):
    """One risk flag with occurrence count."""

    flag: str
    count: int
    pct: float


class IntentCount(BaseModel):
    """One intent with occurrence count."""

    intent: str
    count: int
    pct: float
