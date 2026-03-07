"""Denylist service — check text against per-policy denylist phrases."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.db.session import async_session, get_redis
from src.models.policy import Policy

logger = structlog.get_logger()

CACHE_TTL = 60  # seconds


@dataclass
class DenylistHit:
    """Structured result from a denylist match."""

    phrase: str
    category: str
    action: str  # "block" | "flag" | "score_boost"
    severity: str  # "low" | "medium" | "high" | "critical"
    is_regex: bool
    description: str


async def _load_phrases_from_db(policy_name: str) -> list[dict]:
    """Load denylist phrases for *policy_name* directly from the DB."""
    async with async_session() as session:
        stmt = select(Policy).where(Policy.name == policy_name).options(joinedload(Policy.denylist_phrases))
        result = await session.execute(stmt)
        policy = result.unique().scalar_one_or_none()
        if policy is None:
            return []
        return [
            {
                "phrase": dp.phrase,
                "is_regex": dp.is_regex,
                "category": dp.category,
                "action": dp.action,
                "severity": dp.severity,
                "description": dp.description,
            }
            for dp in policy.denylist_phrases
        ]


async def _get_phrases(policy_name: str) -> list[dict]:
    """Return denylist phrases, preferring Redis cache, falling back to DB."""
    cache_key = f"denylist:{policy_name}"
    try:
        redis = await get_redis()
        cached = await redis.get(cache_key)
        if cached is not None:
            return json.loads(cached)
    except Exception:
        logger.debug("denylist_redis_unavailable", policy=policy_name)

    phrases = await _load_phrases_from_db(policy_name)

    # Write back to cache (best-effort)
    try:
        redis = await get_redis()
        await redis.set(cache_key, json.dumps(phrases), ex=CACHE_TTL)
    except Exception:
        logger.debug("denylist_redis_cache_write_failed", policy=policy_name)

    return phrases


async def check_denylist(text: str, policy_name: str) -> list[DenylistHit]:
    """Check *text* against denylist phrases for *policy_name*.

    Returns a list of DenylistHit objects with action/severity/description.
    """
    phrases = await _get_phrases(policy_name)
    hits: list[DenylistHit] = []
    text_lower = text.lower()
    for p in phrases:
        phrase_str: str = p["phrase"]
        matched = False
        if p.get("is_regex"):
            if re.search(phrase_str, text, re.IGNORECASE):
                matched = True
        else:
            if phrase_str.lower() in text_lower:
                matched = True
        if matched:
            hits.append(
                DenylistHit(
                    phrase=phrase_str,
                    category=p.get("category", "general"),
                    action=p.get("action", "block"),
                    severity=p.get("severity", "medium"),
                    is_regex=p.get("is_regex", False),
                    description=p.get("description", ""),
                )
            )
    return hits
