"""Pydantic schemas for Agent Wizard."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.wizard.models import (
    AccessType,
    AgentEnvironment,
    AgentFramework,
    AgentStatus,
    ProtectionLevel,
    RiskLevel,
    RolloutMode,
    Sensitivity,
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


# ═══════════════════════════════════════════════════════════════════════
# Tool schemas (spec 27a)
# ═══════════════════════════════════════════════════════════════════════


class ToolCreate(BaseModel):
    """Schema for registering a tool on an agent."""

    name: str = Field(..., min_length=2, max_length=128)
    description: str = ""
    category: str | None = None
    access_type: AccessType = AccessType.READ
    sensitivity: Sensitivity = Sensitivity.LOW
    arg_schema: dict | None = None
    returns_pii: bool = False
    returns_secrets: bool = False
    rate_limit: int | None = None


class ToolUpdate(BaseModel):
    """Schema for partial tool update."""

    name: str | None = Field(None, min_length=2, max_length=128)
    description: str | None = None
    category: str | None = None
    access_type: AccessType | None = None
    sensitivity: Sensitivity | None = None
    arg_schema: dict | None = None
    returns_pii: bool | None = None
    returns_secrets: bool | None = None
    rate_limit: int | None = None


class ToolRead(BaseModel):
    """Schema for reading a tool."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    description: str
    category: str | None
    access_type: AccessType
    sensitivity: Sensitivity
    requires_confirmation: bool
    arg_schema: dict | None
    returns_pii: bool
    returns_secrets: bool
    rate_limit: int | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════
# Role schemas (spec 27b)
# ═══════════════════════════════════════════════════════════════════════


class RoleCreate(BaseModel):
    """Schema for creating a role on an agent."""

    name: str = Field(..., min_length=2, max_length=128)
    description: str = ""
    inherits_from: uuid.UUID | None = None


class RoleUpdate(BaseModel):
    """Schema for partial role update."""

    name: str | None = Field(None, min_length=2, max_length=128)
    description: str | None = None
    inherits_from: uuid.UUID | None = None


class PermissionEntry(BaseModel):
    """A single permission assignment for a role–tool pair."""

    tool_id: uuid.UUID
    scopes: list[str] = Field(default_factory=lambda: ["read"])
    requires_confirmation_override: bool | None = None
    conditions: dict | None = None


class PermissionRead(BaseModel):
    """Read view of a role–tool permission."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tool_id: uuid.UUID
    tool_name: str | None = None
    scopes: list[str]
    requires_confirmation_override: bool | None
    conditions: dict | None


class RoleRead(BaseModel):
    """Schema for reading a role (with resolved permissions)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    description: str
    inherits_from: uuid.UUID | None
    permissions: list[PermissionRead] = []
    inherited_permissions: list[PermissionRead] = []
    created_at: datetime


class PermissionBatchSet(BaseModel):
    """Batch set permissions for a role."""

    permissions: list[PermissionEntry]


# ═══════════════════════════════════════════════════════════════════════
# Permission matrix + check (spec 27c)
# ═══════════════════════════════════════════════════════════════════════


class PermissionMatrixResponse(BaseModel):
    """Full role×tool permission matrix."""

    tools: list[str]
    roles: list[str]
    matrix: dict[str, dict[str, str]]


class PermissionCheckResponse(BaseModel):
    """Result of a permission check."""

    allowed: bool
    decision: str  # "allow" | "deny" | "confirm"
    reason: str
