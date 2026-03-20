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
    GateAction,
    GateDecisionType,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    ProtectionLevel,
    RiskLevel,
    RolloutMode,
    Sensitivity,
    TraceDecision,
    TraceGate,
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
    policy_pack: str | None = None


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
    generated_config: dict | None = None
    generated_kit: dict | None = None
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


# ═══════════════════════════════════════════════════════════════════════
# Rollout mode schemas (spec 31)
# ═══════════════════════════════════════════════════════════════════════


class RolloutPromoteRequest(BaseModel):
    """Body for PATCH /agents/:id/rollout."""

    mode: RolloutMode


class RolloutPromoteResponse(BaseModel):
    """Response after a successful promotion/demotion."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    rollout_mode: RolloutMode
    previous_mode: RolloutMode


class PromotionBlockedResponse(BaseModel):
    """Error detail when promotion is blocked."""

    error: str = "promotion_blocked"
    reason: str
    current_mode: RolloutMode
    requested_mode: RolloutMode
    latest_score: dict | None = None


class PromotionEventRead(BaseModel):
    """Read view of a promotion event."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    from_mode: RolloutMode
    to_mode: RolloutMode
    user: str
    created_at: datetime


class ReadinessStats(BaseModel):
    """Promotion readiness statistics."""

    traces_in_current_mode: int
    would_have_blocked: int
    false_positive_rate: float | None = None
    latest_validation: dict | None = None


class ReadinessResponse(BaseModel):
    """Response for GET /agents/:id/rollout/readiness."""

    current_mode: RolloutMode
    can_promote_to: list[RolloutMode]
    blockers: list[str]
    stats: ReadinessStats


# ═══════════════════════════════════════════════════════════════════════
# Gate decision schemas (spec 31b / 31d)
# ═══════════════════════════════════════════════════════════════════════


class GateEvalRequest(BaseModel):
    """Request to evaluate a gate."""

    gate_type: GateDecisionType
    context: dict | None = None


class GateEvalResponse(BaseModel):
    """Result of a gate evaluation."""

    model_config = ConfigDict(from_attributes=True)

    decision: GateAction
    effective_action: GateAction
    rollout_mode: RolloutMode
    enforced: bool
    warning: str | None = None


class GateDecisionRead(BaseModel):
    """Read view of a stored gate decision (trace)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    gate_type: GateDecisionType
    decision: GateAction
    effective_action: GateAction
    rollout_mode: RolloutMode
    enforced: bool
    warning: str | None
    context: dict | None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════
# Agent trace schemas (spec 32)
# ═══════════════════════════════════════════════════════════════════════


class TraceCreate(BaseModel):
    """Request body to record a trace (via recorder service)."""

    session_id: str = "default"
    gate: TraceGate
    tool_name: str | None = None
    role: str | None = None
    decision: TraceDecision
    reason: str = ""
    category: str = "policy"
    rollout_mode: RolloutMode = RolloutMode.OBSERVE
    enforced: bool = True
    latency_ms: int = 0
    details: dict | None = None


class TraceRead(BaseModel):
    """Read view of a single agent trace."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    session_id: str
    timestamp: datetime
    gate: TraceGate
    tool_name: str | None
    role: str | None
    decision: TraceDecision
    reason: str
    category: str
    rollout_mode: RolloutMode
    enforced: bool
    latency_ms: int
    details: dict | None
    incident_id: uuid.UUID | None


class TraceListResponse(BaseModel):
    """Paginated trace list."""

    items: list[TraceRead]
    total: int
    page: int
    per_page: int


# ═══════════════════════════════════════════════════════════════════════
# Incident schemas (spec 32b)
# ═══════════════════════════════════════════════════════════════════════


class IncidentRead(BaseModel):
    """Read view of an agent incident."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    severity: IncidentSeverity
    category: IncidentCategory
    title: str
    status: IncidentStatus
    first_seen: datetime
    last_seen: datetime
    trace_count: int
    details: dict | None


class IncidentListResponse(BaseModel):
    """Paginated incident list."""

    items: list[IncidentRead]
    total: int


class IncidentUpdate(BaseModel):
    """Patch body for incident status update."""

    status: IncidentStatus


# ═══════════════════════════════════════════════════════════════════════
# Trace statistics (spec 32e)
# ═══════════════════════════════════════════════════════════════════════


class IncidentStatsBreakdown(BaseModel):
    open: int = 0
    acknowledged: int = 0
    resolved: int = 0
    false_positive: int = 0


class TraceStatsResponse(BaseModel):
    """Aggregated trace statistics."""

    total_evaluations: int
    by_decision: dict[str, int]
    by_category: dict[str, int]
    by_gate: dict[str, int]
    avg_latency_ms: float
    incidents: IncidentStatsBreakdown


# ═══════════════════════════════════════════════════════════════════════
# Trace Run schemas (structured agent traces — spec tracing)
# ═══════════════════════════════════════════════════════════════════════


class TraceRunCreate(BaseModel):
    """Ingest a full structured agent trace."""

    trace_id: str = Field(..., max_length=64)
    session_id: str = Field(default="default", max_length=128)
    timestamp: datetime | None = None
    user_role: str = Field(default="user", max_length=128)
    model: str = Field(default="", max_length=128)
    intent: str | None = Field(default=None, max_length=128)
    intent_confidence: float = 0.0
    total_duration_ms: int = 0
    counters: dict = Field(default_factory=dict)
    iterations: list[dict] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    limits_hit: str | None = None
    # Overflow: user_message, final_response, policy, node_timings
    user_message: str | None = None
    final_response: str | None = None
    policy: str | None = None
    node_timings: dict | None = None


class TraceRunSummary(BaseModel):
    """Summary view for trace list (no iterations blob)."""

    model_config = ConfigDict(from_attributes=True)

    trace_id: str
    agent_id: uuid.UUID
    session_id: str
    timestamp: datetime
    user_role: str
    model: str
    intent: str | None
    total_duration_ms: int
    iterations_count: int = 0
    tool_calls_count: int = 0
    tool_calls_blocked: int = 0
    firewall_blocked: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    has_errors: bool = False
    limits_hit: str | None


class TraceRunDetail(BaseModel):
    """Full trace detail with iterations."""

    model_config = ConfigDict(from_attributes=True)

    trace_id: str
    agent_id: uuid.UUID
    session_id: str
    timestamp: datetime
    user_role: str
    model: str
    intent: str | None
    intent_confidence: float = 0.0
    total_duration_ms: int
    counters: dict
    iterations: list[dict]
    errors: list
    limits_hit: str | None
    user_message: str | None = None
    final_response: str | None = None
    policy: str | None = None
    node_timings: dict | None = None


class TraceRunListResponse(BaseModel):
    """Paginated trace run list."""

    items: list[TraceRunSummary]
    total: int
    limit: int
    offset: int
