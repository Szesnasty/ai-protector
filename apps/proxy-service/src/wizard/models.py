"""ORM models for the Agent Wizard."""

from __future__ import annotations

import enum
import uuid as _uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base, TimestampMixin, UUIDMixin

# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class AgentFramework(str, enum.Enum):
    """Supported agent frameworks."""

    LANGGRAPH = "langgraph"
    RAW_PYTHON = "raw_python"
    PROXY_ONLY = "proxy_only"


class AgentEnvironment(str, enum.Enum):
    """Deployment environment."""

    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class RiskLevel(str, enum.Enum):
    """Computed risk classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProtectionLevel(str, enum.Enum):
    """Recommended protection level."""

    PROXY_ONLY = "proxy_only"
    AGENT_RUNTIME = "agent_runtime"
    FULL = "full"


class RolloutMode(str, enum.Enum):
    """Agent rollout mode for graduated enforcement."""

    OBSERVE = "observe"
    WARN = "warn"
    ENFORCE = "enforce"


class AgentStatus(str, enum.Enum):
    """Lifecycle status of an agent."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Agent(UUIDMixin, TimestampMixin, Base):
    """Registered agent configuration."""

    __tablename__ = "agents"

    # ── Identity ─────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    team: Mapped[str] = mapped_column(String(64), nullable=True)

    # ── Framework & environment ──────────────────────────────────────
    framework: Mapped[AgentFramework] = mapped_column(
        Enum(AgentFramework, name="agent_framework"),
        nullable=False,
        default=AgentFramework.LANGGRAPH,
    )
    environment: Mapped[AgentEnvironment] = mapped_column(
        Enum(AgentEnvironment, name="agent_environment"),
        nullable=False,
        default=AgentEnvironment.DEV,
    )

    # ── Capability flags (input to risk classification) ──────────────
    is_public_facing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_tools: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    has_write_actions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    touches_pii: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    handles_secrets: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    calls_external_apis: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Computed / chosen fields ─────────────────────────────────────
    risk_level: Mapped[RiskLevel | None] = mapped_column(
        Enum(RiskLevel, name="risk_level"),
        nullable=True,
    )
    protection_level: Mapped[ProtectionLevel | None] = mapped_column(
        Enum(ProtectionLevel, name="protection_level"),
        nullable=True,
    )
    policy_pack: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rollout_mode: Mapped[RolloutMode] = mapped_column(
        Enum(RolloutMode, name="rollout_mode"),
        nullable=False,
        default=RolloutMode.OBSERVE,
    )

    # ── Lifecycle ────────────────────────────────────────────────────
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, name="agent_status"),
        nullable=False,
        default=AgentStatus.DRAFT,
    )
    is_reference: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Generated config cache (spec 28e) ────────────────────────────
    generated_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Generated integration kit cache (spec 29k) ──────────────────
    generated_kit: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<Agent name={self.name!r} risk={self.risk_level} status={self.status}>"


# ═══════════════════════════════════════════════════════════════════════
# Tool enums
# ═══════════════════════════════════════════════════════════════════════


class AccessType(str, enum.Enum):
    """Tool access type."""

    READ = "read"
    WRITE = "write"


class Sensitivity(str, enum.Enum):
    """Tool sensitivity level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ── Smart-default constants ──────────────────────────────────────────

RATE_LIMIT_DEFAULTS: dict[Sensitivity, int] = {
    Sensitivity.LOW: 20,
    Sensitivity.MEDIUM: 10,
    Sensitivity.HIGH: 5,
    Sensitivity.CRITICAL: 3,
}


# ═══════════════════════════════════════════════════════════════════════
# AgentTool (spec 27a)
# ═══════════════════════════════════════════════════════════════════════


class AgentTool(UUIDMixin, TimestampMixin, Base):
    """A tool registered for an agent."""

    __tablename__ = "agent_tools"

    agent_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)

    access_type: Mapped[AccessType] = mapped_column(
        Enum(AccessType, name="access_type"),
        nullable=False,
        default=AccessType.READ,
    )
    sensitivity: Mapped[Sensitivity] = mapped_column(
        Enum(Sensitivity, name="sensitivity"),
        nullable=False,
        default=Sensitivity.LOW,
    )
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    arg_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    returns_pii: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    returns_secrets: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rate_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    agent: Mapped[Agent] = relationship("Agent", backref="tools", lazy="selectin")

    # Unique name per agent
    __table_args__ = (
        # UniqueConstraint handled per-query for better error messages
    )

    def __repr__(self) -> str:
        return f"<AgentTool name={self.name!r} agent_id={self.agent_id}>"


# ═══════════════════════════════════════════════════════════════════════
# AgentRole (spec 27b)
# ═══════════════════════════════════════════════════════════════════════


class AgentRole(UUIDMixin, TimestampMixin, Base):
    """A role defined for an agent (with optional inheritance)."""

    __tablename__ = "agent_roles"

    agent_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    inherits_from: Mapped[_uuid.UUID | None] = mapped_column(
        ForeignKey("agent_roles.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    agent: Mapped[Agent] = relationship("Agent", backref="roles", lazy="selectin")
    parent: Mapped[AgentRole | None] = relationship(
        "AgentRole",
        remote_side="AgentRole.id",
        lazy="selectin",
    )
    permissions: Mapped[list[RoleToolPermission]] = relationship(
        "RoleToolPermission",
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AgentRole name={self.name!r} agent_id={self.agent_id}>"


# ═══════════════════════════════════════════════════════════════════════
# RoleToolPermission (spec 27b)
# ═══════════════════════════════════════════════════════════════════════


class RoleToolPermission(UUIDMixin, Base):
    """Maps a role to a tool with granted scopes."""

    __tablename__ = "role_tool_permissions"

    role_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("agent_roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("agent_tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False, default=lambda: ["read"])
    requires_confirmation_override: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    conditions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    role: Mapped[AgentRole] = relationship("AgentRole", back_populates="permissions")
    tool: Mapped[AgentTool] = relationship("AgentTool", lazy="selectin")

    def __repr__(self) -> str:
        return f"<RoleToolPermission role_id={self.role_id} tool_id={self.tool_id}>"


# ═══════════════════════════════════════════════════════════════════════
# ValidationRun (spec 30c)
# ═══════════════════════════════════════════════════════════════════════


class ValidationRun(UUIDMixin, TimestampMixin, Base):
    """A stored validation run for an agent."""

    __tablename__ = "validation_runs"

    agent_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pack: Mapped[str] = mapped_column(String(64), nullable=False, default="basic")
    pack_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0.0")
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[float] = mapped_column(nullable=False, default=0.0)
    results: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Relationships
    agent: Mapped[Agent] = relationship("Agent", backref="validation_runs", lazy="selectin")

    def __repr__(self) -> str:
        return f"<ValidationRun agent_id={self.agent_id} pack={self.pack} score={self.score}/{self.total}>"


# ═══════════════════════════════════════════════════════════════════════
# PromotionEvent (spec 31c)
# ═══════════════════════════════════════════════════════════════════════


class PromotionEvent(UUIDMixin, TimestampMixin, Base):
    """Audit log entry for rollout mode transitions."""

    __tablename__ = "promotion_events"

    agent_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_mode: Mapped[RolloutMode] = mapped_column(
        Enum(RolloutMode, name="rollout_mode", create_type=False),
        nullable=False,
    )
    to_mode: Mapped[RolloutMode] = mapped_column(
        Enum(RolloutMode, name="rollout_mode", create_type=False),
        nullable=False,
    )
    user: Mapped[str] = mapped_column(String(128), nullable=False, default="system")

    agent: Mapped[Agent] = relationship("Agent", backref="promotion_events", lazy="selectin")

    def __repr__(self) -> str:
        return f"<PromotionEvent {self.from_mode}→{self.to_mode} agent={self.agent_id}>"


# ═══════════════════════════════════════════════════════════════════════
# GateDecision — per-request trace (spec 31b / 31d)
# ═══════════════════════════════════════════════════════════════════════


class GateDecisionType(str, enum.Enum):
    """Type of gate check."""

    RBAC = "rbac"
    INJECTION = "injection"
    PII = "pii"
    BUDGET = "budget"


class GateAction(str, enum.Enum):
    """Gate action result."""

    ALLOW = "allow"
    DENY = "deny"
    BLOCK = "block"
    REDACT = "redact"
    WARN = "warn"


class GateDecision(UUIDMixin, TimestampMixin, Base):
    """Trace of a single gate evaluation."""

    __tablename__ = "gate_decisions"

    agent_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gate_type: Mapped[GateDecisionType] = mapped_column(
        Enum(GateDecisionType, name="gate_decision_type"),
        nullable=False,
    )
    decision: Mapped[GateAction] = mapped_column(
        Enum(GateAction, name="gate_action"),
        nullable=False,
    )
    effective_action: Mapped[GateAction] = mapped_column(
        Enum(GateAction, name="gate_action", create_type=False),
        nullable=False,
    )
    rollout_mode: Mapped[RolloutMode] = mapped_column(
        Enum(RolloutMode, name="rollout_mode", create_type=False),
        nullable=False,
    )
    enforced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    agent: Mapped[Agent] = relationship("Agent", backref="gate_decisions", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<GateDecision gate={self.gate_type} decision={self.decision} "
            f"effective={self.effective_action} enforced={self.enforced}>"
        )


# ═══════════════════════════════════════════════════════════════════════
# Trace enums (spec 32)
# ═══════════════════════════════════════════════════════════════════════


class TraceGate(str, enum.Enum):
    """Which gate produced the trace."""

    PRE_TOOL = "pre_tool"
    POST_TOOL = "post_tool"
    PRE_LLM = "pre_llm"
    POST_LLM = "post_llm"


class TraceDecision(str, enum.Enum):
    """Decision recorded in a trace."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    REDACT = "REDACT"
    WARN = "WARN"


class IncidentSeverity(str, enum.Enum):
    """Incident severity level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentCategory(str, enum.Enum):
    """Incident category."""

    RBAC_VIOLATION = "rbac_violation"
    INJECTION_ATTEMPT = "injection_attempt"
    PII_LEAK = "pii_leak"
    BUDGET_EXCEEDED = "budget_exceeded"


class IncidentStatus(str, enum.Enum):
    """Incident lifecycle status."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


# ═══════════════════════════════════════════════════════════════════════
# AgentIncident (spec 32b) — defined BEFORE AgentTrace so FK works
# ═══════════════════════════════════════════════════════════════════════


class AgentIncident(UUIDMixin, Base):
    """Security incident grouping related traces."""

    __tablename__ = "agent_incidents"

    agent_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity, name="incident_severity"),
        nullable=False,
    )
    category: Mapped[IncidentCategory] = mapped_column(
        Enum(IncidentCategory, name="incident_category"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, name="incident_status"),
        nullable=False,
        default=IncidentStatus.OPEN,
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    trace_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    agent: Mapped[Agent] = relationship("Agent", backref="incidents", lazy="selectin")
    traces: Mapped[list[AgentTrace]] = relationship(
        "AgentTrace",
        back_populates="incident",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AgentIncident severity={self.severity} category={self.category} status={self.status}>"


# ═══════════════════════════════════════════════════════════════════════
# AgentTrace (spec 32a)
# ═══════════════════════════════════════════════════════════════════════


class AgentTrace(UUIDMixin, Base):
    """Per-gate evaluation trace for an agent."""

    __tablename__ = "agent_traces"

    agent_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    gate: Mapped[TraceGate] = mapped_column(
        Enum(TraceGate, name="trace_gate"),
        nullable=False,
    )
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decision: Mapped[TraceDecision] = mapped_column(
        Enum(TraceDecision, name="trace_decision"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="policy")
    rollout_mode: Mapped[RolloutMode] = mapped_column(
        Enum(RolloutMode, name="rollout_mode", create_type=False),
        nullable=False,
    )
    enforced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    incident_id: Mapped[_uuid.UUID | None] = mapped_column(
        ForeignKey("agent_incidents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    agent: Mapped[Agent] = relationship("Agent", backref="traces", lazy="selectin")
    incident: Mapped[AgentIncident | None] = relationship(
        "AgentIncident",
        back_populates="traces",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_agent_traces_agent_timestamp", "agent_id", "timestamp"),
        Index("ix_agent_traces_agent_session", "agent_id", "session_id"),
    )

    def __repr__(self) -> str:
        return f"<AgentTrace gate={self.gate} decision={self.decision} agent={self.agent_id}>"


# ═══════════════════════════════════════════════════════════════════════
# AgentTraceRun — full structured trace per agent request (spec tracing)
# ═══════════════════════════════════════════════════════════════════════


class AgentTraceRun(UUIDMixin, Base):
    """Full structured trace for a single agent request.

    Stores the complete trace dict (iterations, gate decisions, tool
    executions, LLM calls) as JSONB — one row per agent /chat call.
    """

    __tablename__ = "agent_trace_runs"

    agent_id: Mapped[_uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trace_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    session_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="default",
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    user_role: Mapped[str] = mapped_column(String(128), nullable=False, default="user")
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    intent: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    counters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    iterations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    limits_hit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    agent: Mapped[Agent] = relationship("Agent", backref="trace_runs", lazy="selectin")

    __table_args__ = (
        Index("ix_trace_runs_agent_timestamp", "agent_id", "timestamp"),
        Index("ix_trace_runs_agent_session", "agent_id", "session_id"),
    )

    def __repr__(self) -> str:
        return f"<AgentTraceRun trace_id={self.trace_id} agent={self.agent_id}>"
