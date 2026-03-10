"""ORM models for the Agent Wizard."""

from __future__ import annotations

import enum
import uuid as _uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
