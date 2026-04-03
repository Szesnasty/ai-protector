"""RBAC Service — permission resolution with inheritance and scopes.

Spec: docs/archive/agents/02-agents-rbac-allowlist/SPEC.md

Loads role/tool config from YAML, resolves inheritance chains,
checks scopes, and returns structured PermissionResult.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml

from src.agent.rbac.models import (
    PermissionResult,
    RoleConfig,
    ToolDefinition,
    ToolPermission,
)

logger = structlog.get_logger()

# ── Default config path ──────────────────────────────────────────────

_DEFAULT_CONFIG_PATH = Path(__file__).parent / "rbac_config.yaml"

# ── Module-level singleton ────────────────────────────────────────────

_service: RBACService | None = None


class RBACService:
    """In-memory RBAC service loaded from YAML config.

    Provides three main operations:
      - check_permission(role, tool, scope) → PermissionResult
      - get_allowed_tools(role) → list[str]
      - get_role_config(role) → RoleConfig | None
    """

    def __init__(self, config_path: Path | str | None = None) -> None:
        self._roles: dict[str, RoleConfig] = {}
        self._permissions: dict[tuple[str, str], ToolPermission] = {}  # (role, tool)
        self._tool_defs: dict[str, ToolDefinition] = {}

        path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        self._load_config(path)

    # ── Config loading ────────────────────────────────────────────

    def _load_config(self, path: Path) -> None:
        """Parse YAML config into roles, permissions, and tool definitions."""
        with open(path) as f:
            data = yaml.safe_load(f)

        roles_data: dict[str, Any] = data.get("roles", {})

        for role_name, role_info in roles_data.items():
            # Role config
            self._roles[role_name] = RoleConfig(
                name=role_name,
                description=role_info.get("description", ""),
                inherits=role_info.get("inherits"),
                is_active=role_info.get("is_active", True),
            )

            # Tool permissions declared directly on this role
            tools: dict[str, Any] = role_info.get("tools", {})
            for tool_name, tool_info in tools.items():
                scopes = tuple(tool_info.get("scopes", ["read"]))
                sensitivity = tool_info.get("sensitivity", "low")
                requires_confirmation = tool_info.get("requires_confirmation", False)
                rate_limit = tool_info.get("rate_limit")

                self._permissions[(role_name, tool_name)] = ToolPermission(
                    role=role_name,
                    tool=tool_name,
                    scopes=scopes,
                    is_active=True,
                )

                # Register / update tool definition
                if tool_name not in self._tool_defs:
                    self._tool_defs[tool_name] = ToolDefinition(
                        name=tool_name,
                        description="",
                        sensitivity=sensitivity,
                        requires_confirmation=requires_confirmation,
                        rate_limit=rate_limit,
                    )

        logger.info(
            "rbac_config_loaded",
            roles=list(self._roles.keys()),
            permissions=len(self._permissions),
            tool_defs=len(self._tool_defs),
        )

    # ── Inheritance resolution ────────────────────────────────────

    def _resolve_inheritance_chain(self, role_name: str) -> list[str]:
        """Return the role inheritance chain: [role, parent, grandparent, ...].

        Stops at the root (no parent) or if a cycle is detected.
        """
        chain: list[str] = []
        visited: set[str] = set()
        current = role_name

        while current and current not in visited:
            if current not in self._roles:
                break
            visited.add(current)
            chain.append(current)
            current = self._roles[current].inherits  # type: ignore[assignment]

        return chain

    # ── Public API ────────────────────────────────────────────────

    def check_permission(self, role: str, tool: str, scope: str = "read") -> PermissionResult:
        """Check if a role can use a tool with the given scope.

        Resolution order:
        1. Explicit permission for (role, tool).
        2. Walk inheritance chain upward.
        3. If not found → DENY (default-deny).
        4. If found → check scope, is_active, requires_confirmation.
        """
        chain = self._resolve_inheritance_chain(role)

        if not chain:
            return PermissionResult(
                allowed=False,
                reason=f"Unknown role: '{role}'",
            )

        # Walk the chain looking for a permission entry
        permission: ToolPermission | None = None
        for ancestor in chain:
            key = (ancestor, tool)
            if key in self._permissions:
                permission = self._permissions[key]
                break

        if permission is None:
            return PermissionResult(
                allowed=False,
                reason=f"Tool '{tool}' not in allowlist for role '{role}'",
            )

        if not permission.is_active:
            return PermissionResult(
                allowed=False,
                reason=f"Permission for '{tool}' is inactive",
            )

        # Scope check
        if scope not in permission.scopes:
            return PermissionResult(
                allowed=False,
                reason=f"Scope '{scope}' not granted for tool '{tool}' (has: {list(permission.scopes)})",
                scopes_granted=permission.scopes,
            )

        # Resolve tool metadata
        tool_def = self._tool_defs.get(tool)
        sensitivity = tool_def.sensitivity if tool_def else "low"
        requires_confirmation = tool_def.requires_confirmation if tool_def else False

        return PermissionResult(
            allowed=True,
            reason=None,
            requires_confirmation=requires_confirmation,
            tool_sensitivity=sensitivity,
            scopes_granted=permission.scopes,
        )

    def get_allowed_tools(self, role: str) -> list[str]:
        """Return all tool names accessible by role (including inherited)."""
        chain = self._resolve_inheritance_chain(role)
        tools: dict[str, bool] = {}  # Preserve order, deduplicate

        # Walk from most-ancestor to role so direct permissions win
        for ancestor in reversed(chain):
            for (r, t), perm in self._permissions.items():
                if r == ancestor and perm.is_active:
                    tools[t] = True

        return list(tools.keys())

    def get_role_config(self, role: str) -> RoleConfig | None:
        """Return role configuration, or None if unknown."""
        return self._roles.get(role)

    def get_tool_definition(self, tool: str) -> ToolDefinition | None:
        """Return tool definition metadata."""
        return self._tool_defs.get(tool)


# ── Module-level accessors ────────────────────────────────────────────


def get_rbac_service(config_path: Path | str | None = None) -> RBACService:
    """Get or create the singleton RBAC service."""
    global _service
    if _service is None:
        _service = RBACService(config_path)
    return _service


def reset_rbac_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    _service = None
