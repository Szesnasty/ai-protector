"""Tests for /v1/requests endpoints (paginated request log)."""

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
    async with async_session() as session:
        stmt = select(Policy).where(Policy.name == "balanced")
        result = await session.execute(stmt)
        policy = result.scalar_one()
        return policy.id


async def _seed_requests(count: int = 10) -> list[uuid.UUID]:
    """Seed request log entries, return list of IDs."""
    policy_id = await _get_policy_id()
    ids = []
    async with async_session() as session:
        for i in range(count):
            req = Request(
                client_id=f"reqtest-client-{i % 3}",
                policy_id=policy_id,
                intent="injection" if i % 3 == 0 else "benign",
                prompt_preview=f"Request test prompt {i}",
                prompt_hash=f"hash-{i}",
                decision=["BLOCK", "ALLOW", "MODIFY"][i % 3],
                risk_score=round(0.1 * (i + 1), 2),
                latency_ms=20 + i * 5,
                risk_flags={"test_flag": True},
                scanner_results={"scanner": "ok"},
                output_filter_results={"filter": "none"},
                node_timings={"parse": 5, "intent": 10},
                model_used="test-model",
                tokens_in=50 + i,
                tokens_out=100 + i,
                created_at=datetime.now(UTC),
            )
            session.add(req)
            await session.flush()
            ids.append(req.id)
        await session.commit()
    return ids


# ── LIST ─────────────────────────────────────────────────────────────


class TestListRequests:
    @pytest.mark.asyncio
    async def test_list_default(self, client: AsyncClient):
        """GET /v1/requests returns paginated response."""
        await _seed_requests(5)
        resp = await client.get("/v1/requests")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "pages" in data
        assert data["page"] == 1
        assert data["page_size"] == 25

    @pytest.mark.asyncio
    async def test_list_pagination(self, client: AsyncClient):
        """Pagination parameters work correctly."""
        await _seed_requests(10)
        resp = await client.get("/v1/requests", params={"page": 1, "page_size": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 3
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_list_filter_decision(self, client: AsyncClient):
        """Filter by decision."""
        await _seed_requests(10)
        resp = await client.get("/v1/requests", params={"decision": "BLOCK"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["decision"] == "BLOCK"

    @pytest.mark.asyncio
    async def test_list_filter_intent(self, client: AsyncClient):
        """Filter by intent."""
        await _seed_requests(10)
        resp = await client.get("/v1/requests", params={"intent": "injection"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["intent"] == "injection"

    @pytest.mark.asyncio
    async def test_list_filter_client_id(self, client: AsyncClient):
        """Filter by client_id."""
        await _seed_requests(10)
        resp = await client.get("/v1/requests", params={"client_id": "reqtest-client-0"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["client_id"] == "reqtest-client-0"

    @pytest.mark.asyncio
    async def test_list_filter_risk_range(self, client: AsyncClient):
        """Filter by risk_min and risk_max."""
        await _seed_requests(10)
        resp = await client.get(
            "/v1/requests",
            params={"risk_min": 0.3, "risk_max": 0.7},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert 0.3 <= item["risk_score"] <= 0.7

    @pytest.mark.asyncio
    async def test_list_filter_search(self, client: AsyncClient):
        """Search in prompt_preview."""
        await _seed_requests(5)
        resp = await client.get("/v1/requests", params={"search": "Request test prompt"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_filter_date_range(self, client: AsyncClient):
        """Filter by date range."""
        await _seed_requests(5)
        now = datetime.now(UTC).isoformat()
        resp = await client.get(
            "/v1/requests",
            params={"from": "2020-01-01T00:00:00Z", "to": now},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_sort_asc(self, client: AsyncClient):
        """Sort by risk_score ascending."""
        await _seed_requests(5)
        resp = await client.get(
            "/v1/requests",
            params={"sort": "risk_score", "order": "asc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        scores = [item["risk_score"] for item in data["items"] if item["risk_score"] is not None]
        assert scores == sorted(scores)

    @pytest.mark.asyncio
    async def test_list_sort_desc(self, client: AsyncClient):
        """Sort by risk_score descending."""
        await _seed_requests(5)
        resp = await client.get(
            "/v1/requests",
            params={"sort": "risk_score", "order": "desc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        scores = [item["risk_score"] for item in data["items"] if item["risk_score"] is not None]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_list_invalid_sort_uses_default(self, client: AsyncClient):
        """Invalid sort column falls back to created_at."""
        resp = await client.get("/v1/requests", params={"sort": "nonexistent"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_filter_policy_id(self, client: AsyncClient):
        """Filter by policy_id."""
        policy_id = await _get_policy_id()
        await _seed_requests(5)
        resp = await client.get("/v1/requests", params={"policy_id": str(policy_id)})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["policy_id"] == str(policy_id)

    @pytest.mark.asyncio
    async def test_list_includes_policy_name(self, client: AsyncClient):
        """Items include policy_name from relationship."""
        await _seed_requests(3)
        resp = await client.get("/v1/requests")
        assert resp.status_code == 200
        data = resp.json()
        if data["items"]:
            assert "policy_name" in data["items"][0]


# ── DETAIL ───────────────────────────────────────────────────────────


class TestRequestDetail:
    @pytest.mark.asyncio
    async def test_detail_found(self, client: AsyncClient):
        """GET /v1/requests/{id} returns full detail."""
        ids = await _seed_requests(1)
        resp = await client.get(f"/v1/requests/{ids[0]}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(ids[0])
        assert "scanner_results" in data
        assert "output_filter_results" in data
        assert "node_timings" in data
        assert "prompt_hash" in data

    @pytest.mark.asyncio
    async def test_detail_not_found(self, client: AsyncClient):
        """GET /v1/requests/{id} with fake ID returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/v1/requests/{fake_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_detail_includes_policy_name(self, client: AsyncClient):
        """Detail response includes policy_name."""
        ids = await _seed_requests(1)
        resp = await client.get(f"/v1/requests/{ids[0]}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["policy_name"] == "balanced"
