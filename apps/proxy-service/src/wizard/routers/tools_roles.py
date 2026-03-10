"""CRUD router for tools, roles, permissions (Agent Wizard — spec 27)."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.session import get_db
from src.wizard.models import (
    Agent,
    AgentRole,
    AgentTool,
    RoleToolPermission,
)
from src.wizard.schemas import (
    PermissionBatchSet,
    PermissionCheckResponse,
    PermissionMatrixResponse,
    PermissionRead,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    ToolCreate,
    ToolRead,
    ToolUpdate,
)
from src.wizard.services.permissions import (
    build_permission_matrix,
    check_permission,
    detect_circular_inheritance,
    resolve_permissions_for_role,
)
from src.wizard.services.tools import apply_smart_defaults

logger = structlog.get_logger()

router = APIRouter(prefix="/agents/{agent_id}", tags=["tools-roles"])


# ── helpers ─────────────────────────────────────────────────────────────


async def _get_agent_or_404(agent_id: uuid.UUID, db: AsyncSession) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ═══════════════════════════════════════════════════════════════════════
# TOOL CRUD  (spec 27a)
# ═══════════════════════════════════════════════════════════════════════


@router.post("/tools", response_model=ToolRead, status_code=201)
async def create_tool(
    agent_id: uuid.UUID,
    body: ToolCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ToolRead:
    """Register a tool on an agent."""
    await _get_agent_or_404(agent_id, db)

    # Unique name per agent
    existing = await db.execute(select(AgentTool).where(AgentTool.agent_id == agent_id, AgentTool.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Tool '{body.name}' already exists on this agent")

    data = body.model_dump()
    explicit_rate_limit = data.get("rate_limit")  # None means "use smart default"

    tool = AgentTool(agent_id=agent_id, **data)
    if explicit_rate_limit is not None:
        tool.rate_limit = explicit_rate_limit  # keep explicit value
        # Still apply confirmation logic
        from src.wizard.models import AccessType, Sensitivity

        if tool.access_type == AccessType.WRITE and tool.sensitivity in (
            Sensitivity.HIGH,
            Sensitivity.CRITICAL,
        ):
            tool.requires_confirmation = True
    else:
        apply_smart_defaults(tool)

    db.add(tool)
    await db.commit()
    await db.refresh(tool)

    logger.info("tool_created", tool_id=str(tool.id), name=tool.name, agent_id=str(agent_id))
    return tool


@router.get("/tools", response_model=list[ToolRead])
async def list_tools(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[ToolRead]:
    """List all tools for an agent."""
    await _get_agent_or_404(agent_id, db)

    result = await db.execute(select(AgentTool).where(AgentTool.agent_id == agent_id).order_by(AgentTool.name))
    return result.scalars().all()


@router.patch("/tools/{tool_id}", response_model=ToolRead)
async def update_tool(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    body: ToolUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ToolRead:
    """Update a tool. Re-evaluates smart defaults if sensitivity/access_type change."""
    await _get_agent_or_404(agent_id, db)

    tool = await db.get(AgentTool, tool_id)
    if tool is None or tool.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Tool not found")

    update_data = body.model_dump(exclude_unset=True)

    # Unique name check
    if "name" in update_data and update_data["name"] != tool.name:
        existing = await db.execute(
            select(AgentTool).where(AgentTool.agent_id == agent_id, AgentTool.name == update_data["name"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Tool '{update_data['name']}' already exists on this agent")

    for field, value in update_data.items():
        setattr(tool, field, value)

    # Re-apply smart defaults if relevant fields changed
    smart_fields = {"access_type", "sensitivity", "returns_pii", "returns_secrets"}
    if smart_fields & set(update_data.keys()):
        # Re-evaluate confirmation based on new access_type/sensitivity
        from src.wizard.models import AccessType, Sensitivity

        if tool.access_type == AccessType.WRITE and tool.sensitivity in (
            Sensitivity.HIGH,
            Sensitivity.CRITICAL,
        ):
            tool.requires_confirmation = True
        else:
            tool.requires_confirmation = False

    # Only reset rate_limit to default if rate_limit wasn't explicitly set
    if "rate_limit" not in update_data and "sensitivity" in update_data:
        from src.wizard.models import RATE_LIMIT_DEFAULTS

        tool.rate_limit = RATE_LIMIT_DEFAULTS.get(tool.sensitivity)

    await db.commit()
    await db.refresh(tool)

    logger.info("tool_updated", tool_id=str(tool.id), updated_fields=list(update_data.keys()))
    return tool


@router.delete("/tools/{tool_id}", status_code=204)
async def delete_tool(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    """Remove a tool (cascades to permissions)."""
    await _get_agent_or_404(agent_id, db)

    tool = await db.get(AgentTool, tool_id)
    if tool is None or tool.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Tool not found")

    await db.delete(tool)
    await db.commit()

    logger.info("tool_deleted", tool_id=str(tool_id), agent_id=str(agent_id))


# ═══════════════════════════════════════════════════════════════════════
# ROLE CRUD  (spec 27b)
# ═══════════════════════════════════════════════════════════════════════


async def _load_roles_with_chain(agent_id: uuid.UUID, db: AsyncSession) -> list[AgentRole]:
    """Load all roles for an agent with eager-loaded permissions and parent chain.

    Manually wires up the parent references using set_committed_value
    to avoid lazy-loading issues in async context when walking
    multi-level inheritance.
    """
    from sqlalchemy.orm.attributes import set_committed_value

    result = await db.execute(
        select(AgentRole)
        .where(AgentRole.agent_id == agent_id)
        .options(
            selectinload(AgentRole.permissions).selectinload(RoleToolPermission.tool),
        )
        .order_by(AgentRole.name)
    )
    roles = list(result.scalars().unique().all())

    # Build lookup and wire up parent references in-memory
    role_by_id = {r.id: r for r in roles}
    for role in roles:
        parent = role_by_id.get(role.inherits_from) if role.inherits_from else None
        set_committed_value(role, "parent", parent)

    return roles


def _role_to_read(role: AgentRole) -> RoleRead:
    """Convert a role ORM object to RoleRead schema with resolved permissions."""
    own, inherited = resolve_permissions_for_role(role)

    def _perm_to_read(p: RoleToolPermission) -> PermissionRead:
        return PermissionRead(
            id=p.id,
            tool_id=p.tool_id,
            tool_name=p.tool.name if p.tool else None,
            scopes=p.scopes,
            requires_confirmation_override=p.requires_confirmation_override,
            conditions=p.conditions,
        )

    return RoleRead(
        id=role.id,
        agent_id=role.agent_id,
        name=role.name,
        description=role.description,
        inherits_from=role.inherits_from,
        permissions=[_perm_to_read(p) for p in own],
        inherited_permissions=[_perm_to_read(p) for p in inherited],
        created_at=role.created_at,
    )


@router.post("/roles", response_model=RoleRead, status_code=201)
async def create_role(
    agent_id: uuid.UUID,
    body: RoleCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> RoleRead:
    """Create a role on an agent."""
    await _get_agent_or_404(agent_id, db)

    # Unique name per agent
    existing = await db.execute(select(AgentRole).where(AgentRole.agent_id == agent_id, AgentRole.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Role '{body.name}' already exists on this agent")

    # Validate parent exists (if inherits_from is set)
    if body.inherits_from is not None:
        parent = await db.get(AgentRole, body.inherits_from)
        if parent is None or parent.agent_id != agent_id:
            raise HTTPException(status_code=422, detail="Parent role not found on this agent")

    role = AgentRole(agent_id=agent_id, **body.model_dump())
    db.add(role)
    await db.commit()

    # Reload all roles with wired-up parent chain to avoid lazy-load issues
    roles = await _load_roles_with_chain(agent_id, db)
    role = next(r for r in roles if r.name == body.name)

    logger.info("role_created", role_id=str(role.id), name=role.name, agent_id=str(agent_id))
    return _role_to_read(role)


@router.get("/roles", response_model=list[RoleRead])
async def list_roles(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[RoleRead]:
    """List all roles with resolved permissions (including inherited)."""
    await _get_agent_or_404(agent_id, db)
    roles = await _load_roles_with_chain(agent_id, db)
    return [_role_to_read(r) for r in roles]


@router.patch("/roles/{role_id}", response_model=RoleRead)
async def update_role(
    agent_id: uuid.UUID,
    role_id: uuid.UUID,
    body: RoleUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> RoleRead:
    """Update a role."""
    await _get_agent_or_404(agent_id, db)

    role = await db.get(AgentRole, role_id)
    if role is None or role.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Role not found")

    update_data = body.model_dump(exclude_unset=True)

    # Unique name check
    if "name" in update_data and update_data["name"] != role.name:
        existing = await db.execute(
            select(AgentRole).where(AgentRole.agent_id == agent_id, AgentRole.name == update_data["name"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Role '{update_data['name']}' already exists on this agent")

    # Circular inheritance check
    if "inherits_from" in update_data and update_data["inherits_from"] is not None:
        if await detect_circular_inheritance(db, role_id, update_data["inherits_from"]):
            raise HTTPException(status_code=422, detail="Circular inheritance detected")

    for field, value in update_data.items():
        setattr(role, field, value)

    await db.commit()

    # Reload all roles with wired-up parent chain
    roles = await _load_roles_with_chain(agent_id, db)
    role = next(r for r in roles if r.id == role_id)

    logger.info("role_updated", role_id=str(role.id), updated_fields=list(update_data.keys()))
    return _role_to_read(role)


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(
    agent_id: uuid.UUID,
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    """Delete a role. Children's inherits_from set to null (via SET NULL FK)."""
    await _get_agent_or_404(agent_id, db)

    role = await db.get(AgentRole, role_id)
    if role is None or role.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Role not found")

    # Nullify children's inherits_from (explicit, since SA might not track all)
    children = await db.execute(select(AgentRole).where(AgentRole.inherits_from == role_id))
    for child in children.scalars().all():
        child.inherits_from = None

    await db.delete(role)
    await db.commit()

    logger.info("role_deleted", role_id=str(role_id), agent_id=str(agent_id))


# ═══════════════════════════════════════════════════════════════════════
# PERMISSIONS BATCH SET  (spec 27b)
# ═══════════════════════════════════════════════════════════════════════


@router.put("/roles/{role_id}/permissions", response_model=list[PermissionRead], status_code=200)
async def set_permissions(
    agent_id: uuid.UUID,
    role_id: uuid.UUID,
    body: PermissionBatchSet,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[PermissionRead]:
    """Batch-set tool permissions for a role (replace all)."""
    await _get_agent_or_404(agent_id, db)

    role = await db.get(AgentRole, role_id)
    if role is None or role.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Role not found")

    # Validate all tool_ids belong to this agent
    for entry in body.permissions:
        tool = await db.get(AgentTool, entry.tool_id)
        if tool is None or tool.agent_id != agent_id:
            raise HTTPException(
                status_code=422,
                detail=f"Tool '{entry.tool_id}' not found on this agent",
            )

    # Delete existing permissions for this role
    existing = await db.execute(select(RoleToolPermission).where(RoleToolPermission.role_id == role_id))
    for perm in existing.scalars().all():
        await db.delete(perm)

    # Create new permissions
    new_perms: list[RoleToolPermission] = []
    for entry in body.permissions:
        perm = RoleToolPermission(
            role_id=role_id,
            tool_id=entry.tool_id,
            scopes=entry.scopes,
            requires_confirmation_override=entry.requires_confirmation_override,
            conditions=entry.conditions,
        )
        db.add(perm)
        new_perms.append(perm)

    await db.commit()

    # Reload with tool relationship
    result = await db.execute(
        select(RoleToolPermission)
        .where(RoleToolPermission.role_id == role_id)
        .options(selectinload(RoleToolPermission.tool))
    )
    perms = result.scalars().all()

    return [
        PermissionRead(
            id=p.id,
            tool_id=p.tool_id,
            tool_name=p.tool.name if p.tool else None,
            scopes=p.scopes,
            requires_confirmation_override=p.requires_confirmation_override,
            conditions=p.conditions,
        )
        for p in perms
    ]


# ═══════════════════════════════════════════════════════════════════════
# PERMISSION MATRIX  (spec 27c)
# ═══════════════════════════════════════════════════════════════════════


@router.get("/permission-matrix", response_model=PermissionMatrixResponse)
async def get_permission_matrix(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PermissionMatrixResponse:
    """Return the full role×tool permission matrix for an agent."""
    await _get_agent_or_404(agent_id, db)

    # Load tools
    tools_result = await db.execute(select(AgentTool).where(AgentTool.agent_id == agent_id).order_by(AgentTool.name))
    tools = list(tools_result.scalars().all())

    # Load roles with permissions chain
    roles = await _load_roles_with_chain(agent_id, db)

    matrix_data = build_permission_matrix(tools, roles)
    return PermissionMatrixResponse(**matrix_data)


# ═══════════════════════════════════════════════════════════════════════
# PERMISSION CHECK  (spec 27b)
# ═══════════════════════════════════════════════════════════════════════


@router.get("/check-permission", response_model=PermissionCheckResponse)
async def check_permission_endpoint(
    agent_id: uuid.UUID,
    role: str,
    tool: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PermissionCheckResponse:
    """Check if a role has permission to use a tool."""
    await _get_agent_or_404(agent_id, db)

    # Load all roles with full parent chain
    roles = await _load_roles_with_chain(agent_id, db)
    role_obj = next((r for r in roles if r.name == role), None)
    if role_obj is None:
        raise HTTPException(status_code=404, detail=f"Role '{role}' not found")

    # Find tool by name
    tool_result = await db.execute(select(AgentTool).where(AgentTool.agent_id == agent_id, AgentTool.name == tool))
    tool_obj = tool_result.scalar_one_or_none()
    if tool_obj is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool}' not found")

    result = check_permission(role_obj, tool_obj)
    return PermissionCheckResponse(**result)
