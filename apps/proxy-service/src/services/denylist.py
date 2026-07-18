"""Denylist service — check text against per-policy denylist phrases."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import regex  # regex engine with an interruptible timeout (bounds catastrophic backtracking)
import structlog
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.db.session import async_session, get_redis
from src.models.policy import Policy

logger = structlog.get_logger()

CACHE_TTL = 60  # seconds

# Denylist regexes are operator-supplied. Run them defensively so a pathological
# (catastrophic-backtracking) pattern cannot stall the async event loop: the
# match runs off-loop with a wall-clock timeout, and the input is length-capped
# to bound cost. On timeout or an invalid pattern the phrase is treated as a
# non-match (fail open on that single rule, never a hang).
_REGEX_TIMEOUT_S = 0.5
_REGEX_MAX_INPUT = 20_000


def _search_bounded(pattern: str, text: str) -> bool:
    """Run one regex with an interruptible timeout; the match aborts on backtracking blow-up."""
    try:
        return regex.search(pattern, text, regex.IGNORECASE, timeout=_REGEX_TIMEOUT_S) is not None
    except TimeoutError:
        logger.warning("denylist_regex_timeout", pattern=pattern[:80])
        return False
    except regex.error:
        logger.warning("denylist_regex_invalid", pattern=pattern[:80])
        return False


async def _regex_matches(pattern: str, text: str) -> bool:
    """Return whether *pattern* matches *text* without risking an event-loop stall.

    The match runs off-loop in the default executor, and the regex engine's own
    timeout aborts catastrophic backtracking so the worker thread cannot leak.
    """
    capped = text[:_REGEX_MAX_INPUT]
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, _search_bounded, pattern, capped),
            timeout=_REGEX_TIMEOUT_S + 1.0,
        )
    except TimeoutError:
        logger.warning("denylist_regex_timeout_outer", pattern=pattern[:80])
        return False


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
            matched = await _regex_matches(phrase_str, text)
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
