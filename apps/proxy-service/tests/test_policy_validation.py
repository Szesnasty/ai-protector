"""Tests for policy config validation (08b)."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from src.main import app
from src.schemas.policy_config import VALID_NODES, PolicyConfigSchema, ThresholdsSchema


@pytest.fixture
async def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── PolicyConfigSchema unit tests ────────────────────────────────────────


class TestPolicyConfigSchema:
    """Direct Pydantic model validation tests."""

    def test_valid_config(self):
        cfg = PolicyConfigSchema(
            nodes=["llm_guard", "presidio"],
            thresholds=ThresholdsSchema(max_risk=0.5, pii_action="mask"),
        )
        assert cfg.nodes == ["llm_guard", "presidio"]
        assert cfg.thresholds.max_risk == 0.5

    def test_empty_config_defaults(self):
        cfg = PolicyConfigSchema()
        assert cfg.nodes == []
        assert cfg.thresholds.max_risk == 0.7
        assert cfg.thresholds.pii_action == "flag"
        assert cfg.thresholds.enable_canary is False

    def test_invalid_node_name(self):
        with pytest.raises(ValidationError, match="Invalid node names"):
            PolicyConfigSchema(nodes=["foobar"])

    def test_invalid_max_risk_too_high(self):
        with pytest.raises(ValidationError, match="less than or equal to 1"):
            PolicyConfigSchema(thresholds=ThresholdsSchema(max_risk=2.0))

    def test_invalid_max_risk_negative(self):
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            PolicyConfigSchema(thresholds=ThresholdsSchema(max_risk=-0.1))

    def test_invalid_pii_action(self):
        with pytest.raises(ValidationError, match="Input should be"):
            PolicyConfigSchema(
                thresholds=ThresholdsSchema(pii_action="nuke")  # type: ignore[arg-type]
            )

    def test_mixed_valid_invalid_nodes(self):
        with pytest.raises(ValidationError, match="Invalid node names"):
            PolicyConfigSchema(nodes=["llm_guard", "bad_node", "presidio"])

    def test_all_valid_nodes_accepted(self):
        cfg = PolicyConfigSchema(nodes=sorted(VALID_NODES))
        assert set(cfg.nodes) == VALID_NODES

    def test_duplicate_nodes_accepted(self):
        cfg = PolicyConfigSchema(nodes=["llm_guard", "llm_guard"])
        assert cfg.nodes == ["llm_guard", "llm_guard"]


# ── API validation tests ────────────────────────────────────────────────


class TestCreatePolicyValidation:
    """POST /v1/policies config validation."""

    @pytest.mark.asyncio
    async def test_valid_config_accepted(self, client: AsyncClient):
        name = f"val-ok-{uuid.uuid4().hex[:8]}"
        resp = await client.post("/v1/policies", json={
            "name": name,
            "config": {
                "nodes": ["llm_guard"],
                "thresholds": {"max_risk": 0.6},
            },
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_invalid_node_rejected(self, client: AsyncClient):
        name = f"val-bad-{uuid.uuid4().hex[:8]}"
        resp = await client.post("/v1/policies", json={
            "name": name,
            "config": {
                "nodes": ["invalid_scanner"],
                "thresholds": {"max_risk": 0.5},
            },
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_max_risk_too_high_rejected(self, client: AsyncClient):
        name = f"val-risk-{uuid.uuid4().hex[:8]}"
        resp = await client.post("/v1/policies", json={
            "name": name,
            "config": {
                "nodes": [],
                "thresholds": {"max_risk": 5.0},
            },
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_bad_pii_action_rejected(self, client: AsyncClient):
        name = f"val-pii-{uuid.uuid4().hex[:8]}"
        resp = await client.post("/v1/policies", json={
            "name": name,
            "config": {
                "nodes": [],
                "thresholds": {"pii_action": "nuke"},
            },
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_config_uses_defaults(self, client: AsyncClient):
        name = f"val-empty-{uuid.uuid4().hex[:8]}"
        resp = await client.post("/v1/policies", json={
            "name": name,
            "config": {},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["config"] == {}  # stored as-is (validation passed)

    @pytest.mark.asyncio
    async def test_missing_thresholds_accepted(self, client: AsyncClient):
        name = f"val-noth-{uuid.uuid4().hex[:8]}"
        resp = await client.post("/v1/policies", json={
            "name": name,
            "config": {"nodes": ["presidio"]},
        })
        assert resp.status_code == 201


class TestUpdatePolicyValidation:
    """PATCH /v1/policies/{id} config validation."""

    @pytest.mark.asyncio
    async def test_valid_config_update_accepted(self, client: AsyncClient):
        # Create first
        name = f"upd-ok-{uuid.uuid4().hex[:8]}"
        cr = await client.post("/v1/policies", json={
            "name": name,
            "config": {"nodes": [], "thresholds": {"max_risk": 0.9}},
        })
        pid = cr.json()["id"]

        resp = await client.patch(f"/v1/policies/{pid}", json={
            "config": {"nodes": ["llm_guard", "presidio"], "thresholds": {"max_risk": 0.4}},
        })
        assert resp.status_code == 200
        assert resp.json()["config"]["nodes"] == ["llm_guard", "presidio"]

    @pytest.mark.asyncio
    async def test_invalid_config_update_rejected(self, client: AsyncClient):
        name = f"upd-bad-{uuid.uuid4().hex[:8]}"
        cr = await client.post("/v1/policies", json={
            "name": name,
            "config": {"nodes": []},
        })
        pid = cr.json()["id"]

        resp = await client.patch(f"/v1/policies/{pid}", json={
            "config": {"nodes": ["nonexistent"]},
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_version_bumps_on_update(self, client: AsyncClient):
        name = f"ver-{uuid.uuid4().hex[:8]}"
        cr = await client.post("/v1/policies", json={
            "name": name,
            "config": {"nodes": []},
        })
        data = cr.json()
        assert data["version"] == 1

        resp = await client.patch(f"/v1/policies/{data['id']}", json={
            "description": "updated",
        })
        assert resp.json()["version"] == 2

    @pytest.mark.asyncio
    async def test_updated_at_changes_on_patch(self, client: AsyncClient):
        name = f"ts-{uuid.uuid4().hex[:8]}"
        cr = await client.post("/v1/policies", json={
            "name": name,
            "config": {"nodes": []},
        })
        original = cr.json()

        resp = await client.patch(f"/v1/policies/{original['id']}", json={
            "description": "timestamp test",
        })
        updated = resp.json()
        assert updated["updated_at"] is not None
        # updated_at should be >= created_at
        assert updated["updated_at"] >= updated["created_at"]


class TestSeedPoliciesValid:
    """Verify seeded policies pass config validation."""

    @pytest.mark.asyncio
    async def test_all_seeded_policies_have_valid_config(self, client: AsyncClient):
        resp = await client.get("/v1/policies")
        assert resp.status_code == 200
        policies = resp.json()
        for p in policies:
            # Must not raise
            PolicyConfigSchema(**p["config"])

    @pytest.mark.asyncio
    async def test_fast_has_no_scanners(self, client: AsyncClient):
        resp = await client.get("/v1/policies")
        fast = next(p for p in resp.json() if p["name"] == "fast")
        assert fast["config"]["nodes"] == []

    @pytest.mark.asyncio
    async def test_balanced_has_llm_guard(self, client: AsyncClient):
        resp = await client.get("/v1/policies")
        balanced = next(p for p in resp.json() if p["name"] == "balanced")
        assert "llm_guard" in balanced["config"]["nodes"]

    @pytest.mark.asyncio
    async def test_strict_has_presidio(self, client: AsyncClient):
        resp = await client.get("/v1/policies")
        strict = next(p for p in resp.json() if p["name"] == "strict")
        assert "presidio" in strict["config"]["nodes"]
        assert "llm_guard" in strict["config"]["nodes"]
