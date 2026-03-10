"""Agent ORM model for the Agent Wizard."""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


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

    def __repr__(self) -> str:
        return f"<Agent name={self.name!r} risk={self.risk_level} status={self.status}>"
