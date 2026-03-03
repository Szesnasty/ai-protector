"""CRUD router for custom security rules (denylist phrases).

Rules are *global* — they apply to all scanning policies (balanced, strict,
paranoid).  Internally they are stored linked to the canonical "balanced"
policy, but every write is automatically synced to the other scanning
policies so the pipeline sees the same rule-set regardless of which policy
the request uses.
"""

from __future__ import annotations

import re
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db, get_redis
from src.models.denylist import DenylistPhrase
from src.models.policy import Policy
from src.schemas.rule import (
    RuleBulkImport,
    RuleCreate,
    RuleRead,
    RuleTestRequest,
    RuleTestResult,
    RuleUpdate,
)

logger = structlog.get_logger()

router = APIRouter(tags=["rules"])

# Policies that share the same rule-set.
SCANNING_POLICY_NAMES = ("balanced", "strict", "paranoid")
CANONICAL_POLICY = "balanced"


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_canonical_policy(db: AsyncSession) -> Policy:
    """Return the canonical policy used to store rules."""
    stmt = select(Policy).where(Policy.name == CANONICAL_POLICY)
    result = await db.execute(stmt)
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=500, detail="Canonical policy not found")
    return policy


async def _get_scanning_policies(db: AsyncSession) -> list[Policy]:
    """Return all policies that share the rule-set."""
    stmt = select(Policy).where(Policy.name.in_(SCANNING_POLICY_NAMES))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _invalidate_all_caches() -> None:
    """Remove cached denylist for all scanning policies."""
    try:
        redis = await get_redis()
        for name in SCANNING_POLICY_NAMES:
            await redis.delete(f"denylist:{name}")
    except Exception:
        logger.debug("denylist_cache_invalidation_failed")


async def _sync_rule_to_policies(
    db: AsyncSession,
    source_rule: DenylistPhrase,
    policies: list[Policy],
) -> None:
    """Copy a rule to all scanning policies that don't have it yet."""
    for policy in policies:
        if policy.id == source_rule.policy_id:
            continue
        stmt = select(DenylistPhrase).where(
            DenylistPhrase.policy_id == policy.id,
            DenylistPhrase.phrase == source_rule.phrase,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is None:
            clone = DenylistPhrase(
                policy_id=policy.id,
                phrase=source_rule.phrase,
                category=source_rule.category,
                is_regex=source_rule.is_regex,
                action=source_rule.action,
                severity=source_rule.severity,
                description=source_rule.description,
            )
            db.add(clone)


async def _sync_delete_from_policies(
    db: AsyncSession,
    phrase: str,
    policies: list[Policy],
    exclude_policy_id: uuid.UUID,
) -> None:
    """Delete matching phrase from all scanning policies."""
    for policy in policies:
        if policy.id == exclude_policy_id:
            continue
        stmt = select(DenylistPhrase).where(
            DenylistPhrase.policy_id == policy.id,
            DenylistPhrase.phrase == phrase,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            await db.delete(existing)


async def _sync_update_to_policies(
    db: AsyncSession,
    source_rule: DenylistPhrase,
    old_phrase: str,
    policies: list[Policy],
) -> None:
    """Propagate rule updates to all scanning policies."""
    for policy in policies:
        if policy.id == source_rule.policy_id:
            continue
        stmt = select(DenylistPhrase).where(
            DenylistPhrase.policy_id == policy.id,
            DenylistPhrase.phrase == old_phrase,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.phrase = source_rule.phrase
            existing.category = source_rule.category
            existing.is_regex = source_rule.is_regex
            existing.action = source_rule.action
            existing.severity = source_rule.severity
            existing.description = source_rule.description


# ── LIST ─────────────────────────────────────────────────────────────


@router.get("/rules", response_model=list[RuleRead])
async def list_rules(
    category: str | None = Query(None, description="Filter by category (prefix match)"),
    action: str | None = Query(None, description="Filter by action"),
    search: str | None = Query(None, description="Search in phrase or description"),
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[RuleRead]:
    """List all custom security rules."""
    canonical = await _get_canonical_policy(db)

    stmt = (
        select(DenylistPhrase)
        .where(DenylistPhrase.policy_id == canonical.id)
        .order_by(DenylistPhrase.created_at)
    )

    if category:
        stmt = stmt.where(DenylistPhrase.category.like(f"{category}%"))
    if action:
        stmt = stmt.where(DenylistPhrase.action == action)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            DenylistPhrase.phrase.ilike(pattern)
            | DenylistPhrase.description.ilike(pattern)
        )

    result = await db.execute(stmt)
    return result.scalars().all()


# ── CREATE ───────────────────────────────────────────────────────────


@router.post("/rules", response_model=RuleRead, status_code=201)
async def create_rule(
    body: RuleCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> RuleRead:
    """Create a new custom security rule (synced to all scanning policies)."""
    canonical = await _get_canonical_policy(db)

    if body.is_regex:
        try:
            re.compile(body.phrase)
        except re.error as exc:
            raise HTTPException(
                status_code=422, detail=f"Invalid regex: {exc}"
            ) from exc

    rule = DenylistPhrase(policy_id=canonical.id, **body.model_dump())
    db.add(rule)
    await db.flush()

    policies = await _get_scanning_policies(db)
    await _sync_rule_to_policies(db, rule, policies)

    await db.commit()
    await db.refresh(rule)
    await _invalidate_all_caches()
    return rule


# ── UPDATE ───────────────────────────────────────────────────────────


@router.patch("/rules/{rule_id}", response_model=RuleRead)
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> RuleRead:
    """Update an existing rule (synced to all scanning policies)."""
    canonical = await _get_canonical_policy(db)

    rule = await db.get(DenylistPhrase, rule_id)
    if rule is None or rule.policy_id != canonical.id:
        raise HTTPException(status_code=404, detail="Rule not found")

    old_phrase = rule.phrase
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return rule  # type: ignore[return-value]

    new_phrase = update_data.get("phrase", rule.phrase)
    new_is_regex = update_data.get("is_regex", rule.is_regex)
    if new_is_regex:
        try:
            re.compile(new_phrase)
        except re.error as exc:
            raise HTTPException(
                status_code=422, detail=f"Invalid regex: {exc}"
            ) from exc

    for key, value in update_data.items():
        setattr(rule, key, value)

    policies = await _get_scanning_policies(db)
    await _sync_update_to_policies(db, rule, old_phrase, policies)

    await db.commit()
    await db.refresh(rule)
    await _invalidate_all_caches()
    return rule  # type: ignore[return-value]


# ── DELETE ───────────────────────────────────────────────────────────


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    """Delete a rule (synced to all scanning policies)."""
    canonical = await _get_canonical_policy(db)

    rule = await db.get(DenylistPhrase, rule_id)
    if rule is None or rule.policy_id != canonical.id:
        raise HTTPException(status_code=404, detail="Rule not found")

    phrase = rule.phrase
    policies = await _get_scanning_policies(db)
    await _sync_delete_from_policies(db, phrase, policies, canonical.id)

    await db.delete(rule)
    await db.commit()
    await _invalidate_all_caches()


# ── BULK IMPORT ──────────────────────────────────────────────────────


@router.post("/rules/import", response_model=dict, status_code=201)
async def bulk_import_rules(
    body: RuleBulkImport,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """Bulk-import rules. Skips duplicates. Syncs to all scanning policies."""
    canonical = await _get_canonical_policy(db)
    policies = await _get_scanning_policies(db)

    stmt = select(DenylistPhrase.phrase).where(
        DenylistPhrase.policy_id == canonical.id
    )
    result = await db.execute(stmt)
    existing_phrases = {row[0] for row in result.all()}

    created = 0
    skipped = 0
    for rule_data in body.rules:
        if rule_data.phrase in existing_phrases:
            skipped += 1
            continue

        if rule_data.is_regex:
            try:
                re.compile(rule_data.phrase)
            except re.error:
                skipped += 1
                continue

        rule = DenylistPhrase(policy_id=canonical.id, **rule_data.model_dump())
        db.add(rule)
        await db.flush()
        await _sync_rule_to_policies(db, rule, policies)
        existing_phrases.add(rule_data.phrase)
        created += 1

    await db.commit()
    await _invalidate_all_caches()
    return {"created": created, "skipped": skipped}


# ── EXPORT ───────────────────────────────────────────────────────────


@router.get("/rules/export", response_model=list[RuleRead])
async def export_rules(
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[RuleRead]:
    """Export all custom security rules as JSON."""
    canonical = await _get_canonical_policy(db)

    stmt = (
        select(DenylistPhrase)
        .where(DenylistPhrase.policy_id == canonical.id)
        .order_by(DenylistPhrase.created_at)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# ── TEST ─────────────────────────────────────────────────────────────


@router.post("/rules/test", response_model=list[RuleTestResult])
async def test_rules(
    body: RuleTestRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[RuleTestResult]:
    """Test all custom rules against sample text."""
    canonical = await _get_canonical_policy(db)

    stmt = (
        select(DenylistPhrase)
        .where(DenylistPhrase.policy_id == canonical.id)
        .order_by(DenylistPhrase.created_at)
    )
    result = await db.execute(stmt)
    rules = result.scalars().all()

    results: list[RuleTestResult] = []
    text_lower = body.text.lower()

    for rule in rules:
        matched = False
        match_details: str | None = None

        if rule.is_regex:
            m = re.search(rule.phrase, body.text, re.IGNORECASE)
            if m:
                matched = True
                match_details = m.group(0)
        else:
            if rule.phrase.lower() in text_lower:
                matched = True
                match_details = rule.phrase

        if matched:
            results.append(
                RuleTestResult(
                    matched=True,
                    phrase=rule.phrase,
                    category=rule.category,
                    action=rule.action,
                    severity=rule.severity,
                    is_regex=rule.is_regex,
                    description=rule.description,
                    match_details=match_details,
                )
            )

    return results
