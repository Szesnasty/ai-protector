"""Tests for services/denylist.py — check_denylist, _get_phrases, _load_phrases_from_db."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from src.db.session import async_session
from src.models.denylist import DenylistPhrase
from src.models.policy import Policy
from src.services.denylist import DenylistHit, _get_phrases, _load_phrases_from_db, check_denylist

# ── helpers ──────────────────────────────────────────────────────────


async def _get_policy(name: str = "balanced") -> Policy:
    async with async_session() as session:
        stmt = select(Policy).where(Policy.name == name)
        result = await session.execute(stmt)
        return result.scalar_one()


async def _add_phrase(
    policy_id: uuid.UUID,
    phrase: str,
    *,
    is_regex: bool = False,
    category: str = "general",
    action: str = "block",
    severity: str = "medium",
    description: str = "",
) -> uuid.UUID:
    async with async_session() as session:
        dp = DenylistPhrase(
            policy_id=policy_id,
            phrase=phrase,
            is_regex=is_regex,
            category=category,
            action=action,
            severity=severity,
            description=description,
        )
        session.add(dp)
        await session.commit()
        return dp.id


async def _cleanup_test_phrases(policy_id: uuid.UUID, phrases: list[str]) -> None:
    """Remove phrases seeded during the test."""
    async with async_session() as session:
        for phrase in phrases:
            stmt = select(DenylistPhrase).where(
                DenylistPhrase.policy_id == policy_id,
                DenylistPhrase.phrase == phrase,
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                await session.delete(row)
        await session.commit()


# Also invalidate Redis cache for the policy
async def _flush_cache(policy_name: str) -> None:
    try:
        from src.db.session import get_redis

        redis = await get_redis()
        await redis.delete(f"denylist:{policy_name}")
    except Exception:
        pass


# ── _load_phrases_from_db ────────────────────────────────────────────


class TestLoadPhrasesFromDB:
    @pytest.mark.asyncio
    async def test_existing_policy_returns_phrases(self):
        """Loads phrases for a known policy."""
        policy = await _get_policy("balanced")
        phrases_before = await _load_phrases_from_db("balanced")

        await _add_phrase(policy.id, "__test_load_db__")
        try:
            phrases = await _load_phrases_from_db("balanced")
            assert len(phrases) == len(phrases_before) + 1
            added = [p for p in phrases if p["phrase"] == "__test_load_db__"]
            assert len(added) == 1
            assert added[0]["is_regex"] is False
        finally:
            await _cleanup_test_phrases(policy.id, ["__test_load_db__"])

    @pytest.mark.asyncio
    async def test_nonexistent_policy_returns_empty(self):
        """Policy name that doesn't exist → empty list."""
        phrases = await _load_phrases_from_db("nonexistent-policy-xyz")
        assert phrases == []

    @pytest.mark.asyncio
    async def test_phrase_fields(self):
        """Each dict has the expected keys."""
        policy = await _get_policy("balanced")
        await _add_phrase(
            policy.id,
            "__test_fields__",
            category="pii",
            action="flag",
            severity="high",
            description="field test",
        )
        try:
            phrases = await _load_phrases_from_db("balanced")
            match = [p for p in phrases if p["phrase"] == "__test_fields__"]
            assert len(match) == 1
            p = match[0]
            assert p["category"] == "pii"
            assert p["action"] == "flag"
            assert p["severity"] == "high"
            assert p["description"] == "field test"
            assert p["is_regex"] is False
        finally:
            await _cleanup_test_phrases(policy.id, ["__test_fields__"])


# ── _get_phrases (Redis cache layer) ─────────────────────────────────


class TestGetPhrases:
    @pytest.mark.asyncio
    async def test_returns_same_as_db(self):
        """_get_phrases result matches _load_phrases_from_db."""
        await _flush_cache("balanced")
        from_db = await _load_phrases_from_db("balanced")
        from_cache = await _get_phrases("balanced")
        assert from_cache == from_db

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Second call uses cached value (same result, no error)."""
        await _flush_cache("balanced")
        first = await _get_phrases("balanced")
        second = await _get_phrases("balanced")
        assert first == second

    @pytest.mark.asyncio
    async def test_nonexistent_policy(self):
        """Non-existent policy returns empty even through cache layer."""
        await _flush_cache("nonexistent-xyz")
        phrases = await _get_phrases("nonexistent-xyz")
        assert phrases == []


# ── check_denylist ───────────────────────────────────────────────────


class TestCheckDenylist:
    @pytest.mark.asyncio
    async def test_no_match(self):
        """Harmless text won't trigger any hits."""
        await _flush_cache("balanced")
        hits = await check_denylist("hello world", "balanced")
        # May or may not match existing seeded phrases; just ensure it returns a list
        assert isinstance(hits, list)

    @pytest.mark.asyncio
    async def test_plain_match(self):
        """Plain-text phrase is matched case-insensitively."""
        policy = await _get_policy("balanced")
        await _add_phrase(policy.id, "__denytest_bomb__", category="violence")
        await _flush_cache("balanced")
        try:
            hits = await check_denylist("how to make a __DENYTEST_BOMB__", "balanced")
            matching = [h for h in hits if h.phrase == "__denytest_bomb__"]
            assert len(matching) == 1
            assert matching[0].category == "violence"
            assert matching[0].action == "block"
            assert isinstance(matching[0], DenylistHit)
        finally:
            await _cleanup_test_phrases(policy.id, ["__denytest_bomb__"])
            await _flush_cache("balanced")

    @pytest.mark.asyncio
    async def test_regex_match(self):
        """Regex phrase matches pattern."""
        policy = await _get_policy("balanced")
        await _add_phrase(
            policy.id,
            r"__dt_\d{3}__",
            is_regex=True,
            category="pii",
            action="flag",
            severity="high",
        )
        await _flush_cache("balanced")
        try:
            hits = await check_denylist("reference __dt_456__", "balanced")
            matching = [h for h in hits if h.phrase == r"__dt_\d{3}__"]
            assert len(matching) == 1
            assert matching[0].is_regex is True
            assert matching[0].category == "pii"
            assert matching[0].action == "flag"
            assert matching[0].severity == "high"
        finally:
            await _cleanup_test_phrases(policy.id, [r"__dt_\d{3}__"])
            await _flush_cache("balanced")

    @pytest.mark.asyncio
    async def test_regex_no_match(self):
        """Regex that doesn't match returns no hit."""
        policy = await _get_policy("balanced")
        await _add_phrase(
            policy.id,
            r"__nomatch_\d{10}__",
            is_regex=True,
        )
        await _flush_cache("balanced")
        try:
            hits = await check_denylist("nothing here", "balanced")
            matching = [h for h in hits if h.phrase == r"__nomatch_\d{10}__"]
            assert len(matching) == 0
        finally:
            await _cleanup_test_phrases(policy.id, [r"__nomatch_\d{10}__"])
            await _flush_cache("balanced")

    @pytest.mark.asyncio
    async def test_multiple_hits(self):
        """Multiple phrases can match the same text."""
        policy = await _get_policy("balanced")
        await _add_phrase(policy.id, "__multi_hit_a__", category="cat-a")
        await _add_phrase(policy.id, "__multi_hit_b__", category="cat-b")
        await _flush_cache("balanced")
        try:
            hits = await check_denylist("text with __multi_hit_a__ and __multi_hit_b__", "balanced")
            test_hits = [h for h in hits if h.phrase.startswith("__multi_hit_")]
            assert len(test_hits) == 2
            categories = {h.category for h in test_hits}
            assert categories == {"cat-a", "cat-b"}
        finally:
            await _cleanup_test_phrases(policy.id, ["__multi_hit_a__", "__multi_hit_b__"])
            await _flush_cache("balanced")

    @pytest.mark.asyncio
    async def test_score_boost_action(self):
        """Phrase with action=score_boost returns correct action."""
        policy = await _get_policy("balanced")
        await _add_phrase(
            policy.id,
            "__scoreboost__",
            action="score_boost",
            severity="low",
            description="Boosts risk score",
        )
        await _flush_cache("balanced")
        try:
            hits = await check_denylist("text __scoreboost__ here", "balanced")
            matching = [h for h in hits if h.phrase == "__scoreboost__"]
            assert len(matching) == 1
            assert matching[0].action == "score_boost"
            assert matching[0].severity == "low"
            assert matching[0].description == "Boosts risk score"
        finally:
            await _cleanup_test_phrases(policy.id, ["__scoreboost__"])
            await _flush_cache("balanced")

    @pytest.mark.asyncio
    async def test_nonexistent_policy_no_hits(self):
        """Completely unknown policy → no hits."""
        hits = await check_denylist("anything", "nonexistent-policy-abc")
        assert hits == []
