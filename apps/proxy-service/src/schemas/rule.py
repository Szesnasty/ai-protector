"""Pydantic schemas for custom security rules (denylist phrases)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RuleAction(str, Enum):
    """Possible actions when a rule matches."""

    BLOCK = "block"
    FLAG = "flag"
    SCORE_BOOST = "score_boost"


class RuleSeverity(str, Enum):
    """Severity levels for rules."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleCreate(BaseModel):
    """Schema for creating a new rule."""

    phrase: str = Field(..., min_length=1, max_length=1000)
    category: str = Field("general", max_length=64)
    is_regex: bool = False
    action: RuleAction = RuleAction.BLOCK
    severity: RuleSeverity = RuleSeverity.MEDIUM
    description: str = Field("", max_length=256)


class RuleRead(RuleCreate):
    """Schema for reading a rule (includes server-generated fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policy_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class RuleUpdate(BaseModel):
    """Schema for partial rule update."""

    phrase: str | None = Field(None, min_length=1, max_length=1000)
    category: str | None = Field(None, max_length=64)
    is_regex: bool | None = None
    action: RuleAction | None = None
    severity: RuleSeverity | None = None
    description: str | None = Field(None, max_length=256)


class RuleBulkImport(BaseModel):
    """Schema for bulk importing rules."""

    rules: list[RuleCreate] = Field(..., min_length=1, max_length=500)


class RuleTestRequest(BaseModel):
    """Schema for testing rules against sample text."""

    text: str = Field(..., min_length=1, max_length=5000)


class RuleTestResult(BaseModel):
    """Result of a single rule match test."""

    matched: bool
    phrase: str
    category: str
    action: str
    severity: str
    is_regex: bool
    description: str
    match_details: str | None = None
