"""CRUD router for firewall policies."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db, get_redis
from src.models.policy import Policy
from src.schemas.policy import PolicyCreate, PolicyRead, PolicyUpdate
from src.schemas.policy_config import PolicyConfigSchema

logger = structlog.get_logger()

router = APIRouter(tags=["policies"])

BUILTIN_POLICIES = frozenset({"fast", "balanced", "strict", "paranoid"})


def _validate_config(config: dict) -> None:
    """Validate a policy config dict against PolicyConfigSchema.

    Raises HTTPException(422) with Pydantic error details on failure.
    """
    try:
        PolicyConfigSchema(**config)
    except ValidationError as exc:
        # Convert to JSON-safe dicts (Pydantic v2 errors may contain non-serializable objs)
        errors = [
            {
                "loc": list(e.get("loc", [])),
                "msg": e.get("msg", ""),
                "type": e.get("type", ""),
            }
            for e in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=errors) from exc


async def _invalidate_policy_cache(policy_name: str) -> None:
    """Remove cached policy config from Redis after CRUD mutation."""
    try:
        redis = await get_redis()
        await redis.delete(f"policy_config:{policy_name}")
    except Exception:
        logger.debug("policy_cache_invalidation_failed", policy=policy_name)


@router.get("/policies", response_model=list[PolicyRead])
async def list_policies(
    active_only: bool = Query(True),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[PolicyRead]:
    """List all policies.  By default only active ones."""
    stmt = select(Policy).order_by(Policy.name)
    if active_only:
        stmt = stmt.where(Policy.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/policies/{policy_id}", response_model=PolicyRead)
async def get_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PolicyRead:
    """Get a single policy by ID."""
    policy = await db.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.post("/policies", response_model=PolicyRead, status_code=201)
async def create_policy(
    body: PolicyCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PolicyRead:
    """Create a new policy."""
    # Validate config structure
    _validate_config(body.config)

    existing = await db.execute(select(Policy).where(Policy.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Policy '{body.name}' already exists")

    policy = Policy(**body.model_dump())
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.patch("/policies/{policy_id}", response_model=PolicyRead)
async def update_policy(
    policy_id: uuid.UUID,
    body: PolicyUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PolicyRead:
    """Update an existing policy (partial update)."""
    policy = await db.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return policy

    # Validate config if provided
    if "config" in update_data:
        _validate_config(update_data["config"])

    old_name = policy.name
    for key, value in update_data.items():
        setattr(policy, key, value)
    policy.version += 1

    await db.commit()
    await db.refresh(policy)

    # Invalidate Redis cache for old and (possibly new) name
    await _invalidate_policy_cache(old_name)
    if policy.name != old_name:
        await _invalidate_policy_cache(policy.name)

    return policy


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    """Soft-delete a policy (set is_active=False)."""
    policy = await db.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    if policy.name in BUILTIN_POLICIES:
        raise HTTPException(status_code=403, detail="Cannot delete built-in policy")

    policy.is_active = False
    await db.commit()
    await _invalidate_policy_cache(policy.name)
