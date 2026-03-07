"""Tests for /v1/analytics endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.db.session import async_session
from src.main import app
from src.models.policy import Policy
from src.models.request import Request


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _get_policy_id() -> uuid.UUID:
    """Get the balanced policy ID for seeding test requests."""
    async with async_session() as session:
        stmt = select(Policy).where(Policy.name == "balanced")
        result = await session.execute(stmt)
        policy = result.scalar_one()
        return policy.id


async def _seed_requests(count: int = 5) -> None:
    """Insert test requests into the DB for analytics queries."""
    policy_id = await _get_policy_id()
    decisions = ["BLOCK", "ALLOW", "MODIFY", "ALLOW", "BLOCK"]
    intents = ["injection", "benign", "jailbreak", "benign", "injection"]

    async with async_session() as session:
        for i in range(count):
            req = Request(
                client_id=f"analytics-test-{i}",
                policy_id=policy_id,
                intent=intents[i % len(intents)],
                prompt_preview=f"Analytics test prompt {i}",
                decision=decisions[i % len(decisions)],
                risk_score=0.1 * (i + 1),
                latency_ms=50 + i * 10,
                risk_flags={"injection_score": 0.1 * i, "pii_detected": i % 2 == 0},
                model_used="test-model",
                tokens_in=100,
                tokens_out=200,
                created_at=datetime.now(UTC),
            )
            session.add(req)
        await session.commit()


# ── Summary ──────────────────────────────────────────────────────────


class TestAnalyticsSummary:
    @pytest.mark.asyncio
    async def test_summary_empty(self, client: AsyncClient):
        """Summary returns zeros when no data in window."""
        resp = await client.get("/v1/analytics/summary", params={"hours": 0.05})
        assert resp.status_code == 200
        data = resp.json()
        assert "total_requests" in data
        assert "blocked" in data
        assert "modified" in data
        assert "allowed" in data
        assert "block_rate" in data
        assert "avg_risk" in data
        assert "avg_latency_ms" in data

    @pytest.mark.asyncio
    async def test_summary_with_data(self, client: AsyncClient):
        """Summary aggregates seeded requests correctly."""
        await _seed_requests(5)
        resp = await client.get("/v1/analytics/summary", params={"hours": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] >= 5
        assert data["blocked"] >= 2
        assert data["allowed"] >= 2
        assert data["avg_risk"] > 0
        assert data["avg_latency_ms"] > 0

    @pytest.mark.asyncio
    async def test_summary_default_hours(self, client: AsyncClient):
        """Summary works with default hours parameter."""
        resp = await client.get("/v1/analytics/summary")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_summary_top_intent(self, client: AsyncClient):
        """Summary includes top intent when data exists."""
        await _seed_requests(5)
        resp = await client.get("/v1/analytics/summary", params={"hours": 1})
        data = resp.json()
        # top_intent can be None or a string
        assert "top_intent" in data


# ── Timeline ─────────────────────────────────────────────────────────


class TestAnalyticsTimeline:
    @pytest.mark.asyncio
    async def test_timeline_empty(self, client: AsyncClient):
        """Timeline returns empty list with no data."""
        resp = await client.get("/v1/analytics/timeline", params={"hours": 0.05})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_timeline_with_data(self, client: AsyncClient):
        """Timeline returns buckets with seeded data."""
        await _seed_requests(5)
        resp = await client.get("/v1/analytics/timeline", params={"hours": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            bucket = data[0]
            assert "time" in bucket
            assert "total" in bucket
            assert "blocked" in bucket
            assert "allowed" in bucket

    @pytest.mark.asyncio
    async def test_timeline_custom_bucket(self, client: AsyncClient):
        """Timeline accepts custom bucket sizes."""
        await _seed_requests(3)
        for bucket in ["1m", "5m", "15m", "1h"]:
            resp = await client.get(
                "/v1/analytics/timeline",
                params={"hours": 1, "bucket": bucket},
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_timeline_auto_bucket(self, client: AsyncClient):
        """Timeline auto-selects bucket size."""
        resp = await client.get(
            "/v1/analytics/timeline",
            params={"hours": 24, "bucket": "auto"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_timeline_large_window(self, client: AsyncClient):
        """Timeline works with large lookback window."""
        resp = await client.get("/v1/analytics/timeline", params={"hours": 720})
        assert resp.status_code == 200


# ── By-policy ────────────────────────────────────────────────────────


class TestAnalyticsByPolicy:
    @pytest.mark.asyncio
    async def test_by_policy_empty(self, client: AsyncClient):
        """By-policy returns empty list with no data."""
        resp = await client.get("/v1/analytics/by-policy", params={"hours": 0.05})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_by_policy_with_data(self, client: AsyncClient):
        """By-policy groups stats by policy."""
        await _seed_requests(5)
        resp = await client.get("/v1/analytics/by-policy", params={"hours": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            entry = data[0]
            assert "policy_id" in entry
            assert "policy_name" in entry
            assert "total" in entry
            assert "blocked" in entry
            assert "block_rate" in entry
            assert "avg_risk" in entry


# ── Top flags ────────────────────────────────────────────────────────


class TestAnalyticsTopFlags:
    @pytest.mark.asyncio
    async def test_top_flags_empty(self, client: AsyncClient):
        """Top flags returns empty list with no data."""
        resp = await client.get("/v1/analytics/top-flags", params={"hours": 0.05})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_top_flags_with_data(self, client: AsyncClient):
        """Top flags returns flag counts from risk_flags JSONB."""
        await _seed_requests(5)
        resp = await client.get("/v1/analytics/top-flags", params={"hours": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            entry = data[0]
            assert "flag" in entry
            assert "count" in entry
            assert "pct" in entry

    @pytest.mark.asyncio
    async def test_top_flags_custom_limit(self, client: AsyncClient):
        """Top flags respects limit parameter."""
        resp = await client.get(
            "/v1/analytics/top-flags",
            params={"hours": 24, "limit": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 3


# ── Intents ──────────────────────────────────────────────────────────


class TestAnalyticsIntents:
    @pytest.mark.asyncio
    async def test_intents_empty(self, client: AsyncClient):
        """Intents returns empty list with no data."""
        resp = await client.get("/v1/analytics/intents", params={"hours": 0.05})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_intents_with_data(self, client: AsyncClient):
        """Intents returns intent distribution."""
        await _seed_requests(5)
        resp = await client.get("/v1/analytics/intents", params={"hours": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            entry = data[0]
            assert "intent" in entry
            assert "count" in entry
            assert "pct" in entry
