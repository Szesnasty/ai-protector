"""Pydantic schemas for Agent Wizard."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.wizard.models import (
    AgentEnvironment,
    AgentFramework,
    AgentStatus,
    ProtectionLevel,
    RiskLevel,
    RolloutMode,
)


class AgentCreate(BaseModel):
    """Schema for creating a new agent."""

    name: str = Field(..., min_length=2, max_length=128)
    description: str = ""
    team: str | None = None
    framework: AgentFramework = AgentFramework.LANGGRAPH
    environment: AgentEnvironment = AgentEnvironment.DEV
    is_public_facing: bool = False
    has_tools: bool = True
    has_write_actions: bool = False
    touches_pii: bool = False
    handles_secrets: bool = False
    calls_external_apis: bool = False


class AgentUpdate(BaseModel):
    """Schema for partial agent update."""

    name: str | None = Field(None, min_length=2, max_length=128)
    description: str | None = None
    team: str | None = None
    framework: AgentFramework | None = None
    environment: AgentEnvironment | None = None
    is_public_facing: bool | None = None
    has_tools: bool | None = None
    has_write_actions: bool | None = None
    touches_pii: bool | None = None
    handles_secrets: bool | None = None
    calls_external_apis: bool | None = None
    status: AgentStatus | None = None
    policy_pack: str | None = None


class AgentRead(BaseModel):
    """Schema for reading an agent."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    team: str | None
    framework: AgentFramework
    environment: AgentEnvironment
    is_public_facing: bool
    has_tools: bool
    has_write_actions: bool
    touches_pii: bool
    handles_secrets: bool
    calls_external_apis: bool
    risk_level: RiskLevel | None
    protection_level: ProtectionLevel | None
    policy_pack: str | None
    rollout_mode: RolloutMode
    status: AgentStatus
    is_reference: bool
    created_at: datetime
    updated_at: datetime


class AgentListResponse(BaseModel):
    """Paginated agent list response."""

    items: list[AgentRead]
    total: int
    page: int
    per_page: int
