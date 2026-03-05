"""RBAC data models — role, tool definition, permission, and result types.

Spec: docs/agents/02-agents-rbac-allowlist/SPEC.md
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolDefinition:
    """Metadata for a single tool registered in the agent."""

    name: str
    description: str
    category: str = "data_read"  # data_read | data_write | admin | external
    sensitivity: str = "low"  # low | medium | high | critical
    requires_confirmation: bool = False
    rate_limit: int | None = None  # Max calls per session (→ spec 06)


@dataclass(frozen=True)
class ToolPermission:
    """A single role→tool permission entry."""

    role: str
    tool: str
    scopes: tuple[str, ...] = ("read",)
    is_active: bool = True


@dataclass(frozen=True)
class RoleConfig:
    """Full configuration for one role."""

    name: str
    description: str = ""
    inherits: str | None = None
    is_active: bool = True


@dataclass(frozen=True)
class PermissionResult:
    """Outcome of a permission check."""

    allowed: bool
    reason: str | None = None
    requires_confirmation: bool = False
    tool_sensitivity: str = "low"
    scopes_granted: tuple[str, ...] = ()
