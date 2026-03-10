"""Permission resolution service for roles with inheritance (spec 27b-c)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from src.wizard.models import AgentRole, AgentTool, RoleToolPermission


async def detect_circular_inheritance(
    session: AsyncSession,
    role_id: uuid.UUID,
    proposed_parent_id: uuid.UUID | None,
) -> bool:
    """Return True if setting `role_id.inherits_from = proposed_parent_id`
    would create a cycle.

    Walk up from proposed_parent_id to the root; if we encounter role_id
    anywhere, there is a cycle.
    """
    if proposed_parent_id is None:
        return False

    if proposed_parent_id == role_id:
        return True

    from src.wizard.models import AgentRole  # noqa: F811

    visited: set[uuid.UUID] = {role_id}
    current_id = proposed_parent_id

    while current_id is not None:
        if current_id in visited:
            return True
        visited.add(current_id)
        result = await session.execute(select(AgentRole.inherits_from).where(AgentRole.id == current_id))
        row = result.one_or_none()
        if row is None:
            break
        current_id = row[0]

    return False


def resolve_permissions_for_role(
    role: AgentRole,
    *,
    _visited: set[uuid.UUID] | None = None,
) -> tuple[list[RoleToolPermission], list[RoleToolPermission]]:
    """Return (own_permissions, inherited_permissions) for a role.

    Walks up the inheritance chain. Child overrides win (keyed by tool_id).
    _visited prevents accidental infinite loop (should never happen if
    circular check is enforced).
    """
    if _visited is None:
        _visited = set()

    if role.id in _visited:  # safety guard
        return [], []
    _visited.add(role.id)

    own = list(role.permissions)
    own_tool_ids = {p.tool_id for p in own}

    inherited: list[RoleToolPermission] = []
    if role.parent is not None:
        _, parent_all = _collect_all_permissions(role.parent, _visited=_visited)
        for p in parent_all:
            if p.tool_id not in own_tool_ids:
                inherited.append(p)

    return own, inherited


def _collect_all_permissions(
    role: AgentRole,
    *,
    _visited: set[uuid.UUID] | None = None,
) -> tuple[set[uuid.UUID], list[RoleToolPermission]]:
    """Collect all effective permissions (own + inherited, child wins)."""
    if _visited is None:
        _visited = set()

    if role.id in _visited:
        return set(), []
    _visited.add(role.id)

    all_perms: dict[uuid.UUID, RoleToolPermission] = {}

    # Parent first (so child overrides)
    if role.parent is not None:
        _, parent_perms = _collect_all_permissions(role.parent, _visited=_visited)
        for p in parent_perms:
            all_perms[p.tool_id] = p

    # Own override parent
    for p in role.permissions:
        all_perms[p.tool_id] = p

    return set(all_perms.keys()), list(all_perms.values())


def build_permission_matrix(
    tools: list[AgentTool],
    roles: list[AgentRole],
) -> dict:
    """Build a role×tool permission matrix.

    Returns dict with keys: tools, roles, matrix.
    Matrix values: "allow" | "deny" | "confirm".
    """
    tool_names = [t.name for t in tools]
    role_names = [r.name for r in roles]

    matrix: dict[str, dict[str, str]] = {}

    for role in roles:
        _, all_perms = _collect_all_permissions(role, _visited=set())
        perm_by_tool: dict[uuid.UUID, RoleToolPermission] = {p.tool_id: p for p in all_perms}

        row: dict[str, str] = {}
        for tool in tools:
            perm = perm_by_tool.get(tool.id)
            if perm is None:
                row[tool.name] = "deny"
            else:
                # Check confirmation: permission override > tool default
                needs_confirm = (
                    perm.requires_confirmation_override
                    if perm.requires_confirmation_override is not None
                    else tool.requires_confirmation
                )
                row[tool.name] = "confirm" if needs_confirm else "allow"

        matrix[role.name] = row

    return {
        "tools": tool_names,
        "roles": role_names,
        "matrix": matrix,
    }


def check_permission(
    role: AgentRole,
    tool: AgentTool,
) -> dict:
    """Check whether a role has access to a tool.

    Returns dict with keys: allowed, decision, reason.
    """
    _, all_perms = _collect_all_permissions(role, _visited=set())
    perm_by_tool = {p.tool_id: p for p in all_perms}

    perm = perm_by_tool.get(tool.id)
    if perm is None:
        return {
            "allowed": False,
            "decision": "deny",
            "reason": f"Role '{role.name}' has no permission for tool '{tool.name}'",
        }

    needs_confirm = (
        perm.requires_confirmation_override
        if perm.requires_confirmation_override is not None
        else tool.requires_confirmation
    )

    if needs_confirm:
        return {
            "allowed": True,
            "decision": "confirm",
            "reason": f"Role '{role.name}' may use tool '{tool.name}' with confirmation",
        }

    return {
        "allowed": True,
        "decision": "allow",
        "reason": f"Role '{role.name}' is allowed to use tool '{tool.name}'",
    }
