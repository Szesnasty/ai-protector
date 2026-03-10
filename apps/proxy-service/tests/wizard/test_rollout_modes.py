"""Tests for Rollout Modes — spec 31 (48 tests).

Covers:
  31a — DB model + enum (6 tests)
  31b — Gate behavior changes (18 tests)
  31c — Promotion API (14 tests)
  31d — Rollout mode in traces (6 tests)
  31e — Promotion readiness (4 tests)
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from src.db.session import async_session
from src.main import app
from src.wizard.models import (
    Agent,
    RolloutMode,
    ValidationRun,
)
from src.wizard.schemas import AgentRead


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Helpers ──────────────────────────────────────────────────────────

_AGENT_BODY = {
    "name": "RolloutTestAgent",
    "description": "Agent for rollout mode tests",
    "team": "security",
    "framework": "langgraph",
    "environment": "dev",
    "is_public_facing": True,
    "has_tools": True,
    "has_write_actions": True,
    "touches_pii": True,
    "handles_secrets": False,
    "calls_external_apis": False,
}


async def _create_agent(client: AsyncClient, **overrides) -> dict:
    body = {**_AGENT_BODY, "name": f"RolloutAgent-{uuid.uuid4().hex[:8]}", **overrides}
    resp = await client.post("/v1/agents", json=body)
    assert resp.status_code == 201
    return resp.json()


async def _create_tool(client: AsyncClient, agent_id: str) -> dict:
    body = {"name": f"tool-{uuid.uuid4().hex[:8]}", "description": "test tool"}
    resp = await client.post(f"/v1/agents/{agent_id}/tools", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_role(client: AsyncClient, agent_id: str) -> dict:
    body = {"name": f"role-{uuid.uuid4().hex[:8]}", "description": "test role"}
    resp = await client.post(f"/v1/agents/{agent_id}/roles", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _setup_full_agent(client: AsyncClient) -> dict:
    """Create agent with tool, role, permission, generated config."""
    agent = await _create_agent(client)
    aid = agent["id"]
    tool = await _create_tool(client, aid)
    role = await _create_role(client, aid)

    # Set permission
    await client.put(
        f"/v1/agents/{aid}/roles/{role['id']}/permissions",
        json={"permissions": [{"tool_id": tool["id"], "scopes": ["read", "write"]}]},
    )
    # Generate config
    await client.post(f"/v1/agents/{aid}/config/generate")
    return agent


async def _run_validation(client: AsyncClient, agent_id: str, pack: str = "basic") -> dict:
    resp = await client.post(f"/v1/agents/{agent_id}/validate", json={"pack": pack})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _inject_validation_run(agent_id: str, passed: int, total: int) -> None:
    """Directly insert a validation run into the DB."""
    async with async_session() as db:
        run = ValidationRun(
            agent_id=uuid.UUID(agent_id),
            pack="basic",
            pack_version="1.0.0",
            score=int(passed / total * 100) if total > 0 else 0,
            total=total,
            passed=passed,
            failed=total - passed,
            duration_ms=50.0,
            results={"tests": [], "categories": {}, "run_at": "2026-01-01T00:00:00"},
        )
        db.add(run)
        await db.commit()


async def _promote(client: AsyncClient, agent_id: str, mode: str) -> ...:
    return await client.patch(f"/v1/agents/{agent_id}/rollout", json={"mode": mode})


async def _eval_gate(client: AsyncClient, agent_id: str, gate: str, **ctx) -> ...:
    return await client.post(
        f"/v1/agents/{agent_id}/gate/evaluate",
        json={"gate_type": gate, "context": ctx or None},
    )


# ═══════════════════════════════════════════════════════════════════════
# 31a — DB model + enum (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestRolloutModelEnum:
    """31a — DB model + enum."""

    async def test_rollout_enum_values(self):
        """RolloutMode has observe, warn, enforce."""
        assert set(RolloutMode) == {
            RolloutMode.OBSERVE,
            RolloutMode.WARN,
            RolloutMode.ENFORCE,
        }

    async def test_new_agent_default_observe(self, client: AsyncClient):
        """New agent defaults to rollout_mode=OBSERVE."""
        agent = await _create_agent(client)
        assert agent["rollout_mode"] == "observe"

    async def test_migration_existing_agents(self, client: AsyncClient):
        """Agents created without explicit rollout_mode get OBSERVE."""
        agent = await _create_agent(client)
        resp = await client.get(f"/v1/agents/{agent['id']}")
        assert resp.status_code == 200
        assert resp.json()["rollout_mode"] == "observe"

    async def test_agent_read_includes_rollout(self):
        """AgentRead schema has rollout_mode field."""
        fields = AgentRead.model_fields
        assert "rollout_mode" in fields

    async def test_invalid_enum_value(self, client: AsyncClient):
        """Setting rollout_mode to invalid value returns error."""
        agent = await _create_agent(client)
        resp = await _promote(client, agent["id"], "xxx")
        assert resp.status_code == 422

    async def test_enum_string_values(self):
        """Enum string values match spec."""
        assert RolloutMode.OBSERVE.value == "observe"
        assert RolloutMode.WARN.value == "warn"
        assert RolloutMode.ENFORCE.value == "enforce"


# ═══════════════════════════════════════════════════════════════════════
# 31b — Gate behavior changes (18 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGateBehavior:
    """31b — Gate behavior changes per rollout mode."""

    # ── OBSERVE mode ─────────────────────────────────────────────

    async def test_observe_rbac_deny_allows(self, client: AsyncClient):
        """OBSERVE + RBAC deny → action ALLOWED."""
        agent = await _create_agent(client)
        resp = await _eval_gate(client, agent["id"], "rbac")
        assert resp.status_code == 200
        data = resp.json()
        assert data["effective_action"] == "allow"

    async def test_observe_rbac_deny_traces(self, client: AsyncClient):
        """OBSERVE + RBAC deny → trace with decision=deny, enforced=false."""
        agent = await _create_agent(client)
        resp = await _eval_gate(client, agent["id"], "rbac")
        data = resp.json()
        assert data["decision"] == "deny"
        assert data["enforced"] is False

    async def test_observe_injection_allows(self, client: AsyncClient):
        """OBSERVE + injection detected → action ALLOWED."""
        agent = await _create_agent(client)
        resp = await _eval_gate(client, agent["id"], "injection")
        data = resp.json()
        assert data["effective_action"] == "allow"

    async def test_observe_injection_traces(self, client: AsyncClient):
        """OBSERVE + injection → trace with decision=block, enforced=false."""
        agent = await _create_agent(client)
        resp = await _eval_gate(client, agent["id"], "injection")
        data = resp.json()
        assert data["decision"] == "block"
        assert data["enforced"] is False

    async def test_observe_pii_passes_through(self, client: AsyncClient):
        """OBSERVE + PII in output → not redacted, pass-through."""
        agent = await _create_agent(client)
        resp = await _eval_gate(client, agent["id"], "pii")
        data = resp.json()
        assert data["effective_action"] == "allow"
        assert data["decision"] == "redact"

    async def test_observe_budget_allows(self, client: AsyncClient):
        """OBSERVE + over limit → action ALLOWED."""
        agent = await _create_agent(client)
        resp = await _eval_gate(client, agent["id"], "budget")
        data = resp.json()
        assert data["effective_action"] == "allow"

    # ── WARN mode ────────────────────────────────────────────────

    async def test_warn_rbac_deny_allows(self, client: AsyncClient):
        """WARN + RBAC deny → action ALLOWED + warning."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        resp = await _eval_gate(client, agent["id"], "rbac")
        data = resp.json()
        assert data["effective_action"] == "allow"

    async def test_warn_rbac_deny_has_warning(self, client: AsyncClient):
        """WARN + RBAC deny → warning field present."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        resp = await _eval_gate(client, agent["id"], "rbac")
        data = resp.json()
        assert data["warning"] is not None
        assert "AI-Protector" in data["warning"]
        assert "deny" in data["warning"]

    async def test_warn_injection_allows_with_warning(self, client: AsyncClient):
        """WARN + injection → ALLOWED + warning."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        resp = await _eval_gate(client, agent["id"], "injection")
        data = resp.json()
        assert data["effective_action"] == "allow"
        assert data["warning"] is not None

    async def test_warn_pii_passes_with_warning(self, client: AsyncClient):
        """WARN + PII → not redacted + warning."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        resp = await _eval_gate(client, agent["id"], "pii")
        data = resp.json()
        assert data["effective_action"] == "allow"
        assert data["warning"] is not None

    async def test_warn_budget_allows_with_warning(self, client: AsyncClient):
        """WARN + over limit → ALLOWED + warning."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        resp = await _eval_gate(client, agent["id"], "budget")
        data = resp.json()
        assert data["effective_action"] == "allow"
        assert data["warning"] is not None

    # ── ENFORCE mode ─────────────────────────────────────────────

    async def test_enforce_rbac_denies(self, client: AsyncClient):
        """ENFORCE + RBAC deny → DENIED."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        await _promote(client, agent["id"], "enforce")
        resp = await _eval_gate(client, agent["id"], "rbac")
        data = resp.json()
        assert data["effective_action"] == "deny"

    async def test_enforce_injection_blocks(self, client: AsyncClient):
        """ENFORCE + injection → BLOCKED."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        await _promote(client, agent["id"], "enforce")
        resp = await _eval_gate(client, agent["id"], "injection")
        data = resp.json()
        assert data["effective_action"] == "block"

    async def test_enforce_pii_redacts(self, client: AsyncClient):
        """ENFORCE + PII → REDACTED."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        await _promote(client, agent["id"], "enforce")
        resp = await _eval_gate(client, agent["id"], "pii")
        data = resp.json()
        assert data["effective_action"] == "redact"

    async def test_enforce_budget_denies(self, client: AsyncClient):
        """ENFORCE + over limit → DENIED."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        await _promote(client, agent["id"], "enforce")
        resp = await _eval_gate(client, agent["id"], "budget")
        data = resp.json()
        assert data["effective_action"] == "deny"

    async def test_enforce_traces_enforced_true(self, client: AsyncClient):
        """ENFORCE traces have enforced=true."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        await _promote(client, agent["id"], "enforce")
        resp = await _eval_gate(client, agent["id"], "rbac")
        data = resp.json()
        assert data["enforced"] is True

    async def test_same_request_3_modes(self, client: AsyncClient):
        """Identical RBAC check in 3 modes → same decision, different enforcement."""
        # OBSERVE
        a1 = await _create_agent(client)
        r1 = (await _eval_gate(client, a1["id"], "rbac")).json()

        # WARN
        a2 = await _create_agent(client)
        await _inject_validation_run(a2["id"], 12, 12)
        await _promote(client, a2["id"], "warn")
        r2 = (await _eval_gate(client, a2["id"], "rbac")).json()

        # ENFORCE
        a3 = await _create_agent(client)
        await _inject_validation_run(a3["id"], 12, 12)
        await _promote(client, a3["id"], "warn")
        await _promote(client, a3["id"], "enforce")
        r3 = (await _eval_gate(client, a3["id"], "rbac")).json()

        # Same decision
        assert r1["decision"] == r2["decision"] == r3["decision"] == "deny"
        # Different enforcement
        assert r1["enforced"] is False
        assert r2["enforced"] is False
        assert r3["enforced"] is True
        # Different effective action
        assert r1["effective_action"] == "allow"
        assert r2["effective_action"] == "allow"
        assert r3["effective_action"] == "deny"

    async def test_trace_has_rollout_mode(self, client: AsyncClient):
        """Every trace includes rollout_mode field."""
        agent = await _create_agent(client)
        resp = await _eval_gate(client, agent["id"], "rbac")
        data = resp.json()
        assert "rollout_mode" in data
        assert data["rollout_mode"] == "observe"


# ═══════════════════════════════════════════════════════════════════════
# 31c — Promotion API (14 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestPromotionAPI:
    """31c — Promotion API."""

    async def test_promote_observe_to_warn(self, client: AsyncClient):
        """PATCH mode=warn from observe → 200 (with validation present)."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 10, 12)
        resp = await _promote(client, agent["id"], "warn")
        assert resp.status_code == 200
        assert resp.json()["rollout_mode"] == "warn"

    async def test_promote_warn_to_enforce(self, client: AsyncClient):
        """PATCH mode=enforce from warn → 200 (100% validation)."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        resp = await _promote(client, agent["id"], "enforce")
        assert resp.status_code == 200
        assert resp.json()["rollout_mode"] == "enforce"

    async def test_promote_observe_to_enforce_blocked(self, client: AsyncClient):
        """PATCH mode=enforce from observe → 422, skip not allowed."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        resp = await _promote(client, agent["id"], "enforce")
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "promotion_blocked"
        assert "warn first" in detail["reason"].lower() or "warn" in detail["reason"].lower()

    async def test_promote_warn_to_enforce_low_score(self, client: AsyncClient):
        """validation 10/12 → 422 with score details."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        # Now inject a low score as the "latest"
        await _inject_validation_run(agent["id"], 10, 12)
        resp = await _promote(client, agent["id"], "enforce")
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "promotion_blocked"
        assert detail["latest_score"]["passed"] == 10
        assert detail["latest_score"]["total"] == 12

    async def test_promote_warn_to_enforce_no_validation(self, client: AsyncClient):
        """No validation run → 422."""
        agent = await _create_agent(client)
        # Manually set to warn without going through promote (hack for test)
        async with async_session() as db:
            a = await db.get(Agent, uuid.UUID(agent["id"]))
            a.rollout_mode = RolloutMode.WARN
            await db.commit()

        resp = await _promote(client, agent["id"], "enforce")
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "no validation" in detail["reason"].lower()

    async def test_demote_enforce_to_warn(self, client: AsyncClient):
        """PATCH mode=warn from enforce → 200."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        await _promote(client, agent["id"], "enforce")
        resp = await _promote(client, agent["id"], "warn")
        assert resp.status_code == 200
        assert resp.json()["rollout_mode"] == "warn"

    async def test_demote_warn_to_observe(self, client: AsyncClient):
        """PATCH mode=observe from warn → 200."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        resp = await _promote(client, agent["id"], "observe")
        assert resp.status_code == 200
        assert resp.json()["rollout_mode"] == "observe"

    async def test_demote_enforce_to_observe(self, client: AsyncClient):
        """PATCH mode=observe from enforce → 200 (downgrade always allowed)."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        await _promote(client, agent["id"], "enforce")
        resp = await _promote(client, agent["id"], "observe")
        assert resp.status_code == 200
        assert resp.json()["rollout_mode"] == "observe"

    async def test_promote_same_mode(self, client: AsyncClient):
        """PATCH current mode → 200 (no-op)."""
        agent = await _create_agent(client)
        resp = await _promote(client, agent["id"], "observe")
        assert resp.status_code == 200
        assert resp.json()["rollout_mode"] == "observe"
        assert resp.json()["previous_mode"] == "observe"

    async def test_promote_invalid_mode(self, client: AsyncClient):
        """PATCH mode='xxx' → 422."""
        agent = await _create_agent(client)
        resp = await _promote(client, agent["id"], "xxx")
        assert resp.status_code == 422

    async def test_promote_nonexistent_agent(self, client: AsyncClient):
        """PATCH bad ID → 404."""
        fake_id = str(uuid.uuid4())
        resp = await _promote(client, fake_id, "warn")
        assert resp.status_code == 404

    async def test_promotion_event_stored(self, client: AsyncClient):
        """After promote, event in DB with from/to/timestamp."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")

        resp = await client.get(f"/v1/agents/{agent['id']}/rollout/events")
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 1
        latest = events[0]
        assert latest["from_mode"] == "observe"
        assert latest["to_mode"] == "warn"
        assert "created_at" in latest

    async def test_promotion_events_history(self, client: AsyncClient):
        """GET promotion events → ordered list."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        await _promote(client, agent["id"], "enforce")

        resp = await client.get(f"/v1/agents/{agent['id']}/rollout/events")
        events = resp.json()
        assert len(events) == 2
        # Most recent first
        assert events[0]["to_mode"] == "enforce"
        assert events[1]["to_mode"] == "warn"

    async def test_returns_updated_agent(self, client: AsyncClient):
        """PATCH response includes full agent info with new rollout_mode."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        resp = await _promote(client, agent["id"], "warn")
        data = resp.json()
        assert data["id"] == agent["id"]
        assert data["name"] == agent["name"]
        assert data["rollout_mode"] == "warn"
        assert data["previous_mode"] == "observe"


# ═══════════════════════════════════════════════════════════════════════
# 31d — Rollout mode in traces (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestTracesRolloutMode:
    """31d — Rollout mode in traces."""

    async def test_trace_observe_mode_field(self, client: AsyncClient):
        """Trace in observe → rollout_mode='observe'."""
        agent = await _create_agent(client)
        await _eval_gate(client, agent["id"], "rbac")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces")
        traces = resp.json()
        assert len(traces) >= 1
        assert traces[0]["rollout_mode"] == "observe"

    async def test_trace_warn_mode_field(self, client: AsyncClient):
        """Trace in warn → rollout_mode='warn'."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        await _eval_gate(client, agent["id"], "rbac")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces")
        traces = resp.json()
        assert any(t["rollout_mode"] == "warn" for t in traces)

    async def test_trace_enforce_mode_field(self, client: AsyncClient):
        """Trace in enforce → rollout_mode='enforce'."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        await _promote(client, agent["id"], "enforce")
        await _eval_gate(client, agent["id"], "rbac")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces")
        traces = resp.json()
        assert any(t["rollout_mode"] == "enforce" for t in traces)

    async def test_filter_traces_by_mode(self, client: AsyncClient):
        """GET ?rollout_mode=observe → only observe traces."""
        agent = await _create_agent(client)
        # Create traces in observe
        await _eval_gate(client, agent["id"], "rbac")
        await _eval_gate(client, agent["id"], "injection")

        # Promote to warn and create more
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")
        await _eval_gate(client, agent["id"], "rbac")

        # Filter by observe only
        resp = await client.get(f"/v1/agents/{agent['id']}/traces?rollout_mode=observe")
        traces = resp.json()
        assert len(traces) == 2
        assert all(t["rollout_mode"] == "observe" for t in traces)

    async def test_filter_enforced_false_deny(self, client: AsyncClient):
        """GET ?enforced=false&decision=deny → FP candidates."""
        agent = await _create_agent(client)
        # OBSERVE mode: RBAC deny is not enforced
        await _eval_gate(client, agent["id"], "rbac")

        resp = await client.get(f"/v1/agents/{agent['id']}/traces?enforced=false&decision=deny")
        traces = resp.json()
        assert len(traces) >= 1
        for t in traces:
            assert t["enforced"] is False
            assert t["decision"] == "deny"

    async def test_trace_mode_at_evaluation_time(self, client: AsyncClient):
        """Promote mid-session → old traces keep old mode."""
        agent = await _create_agent(client)

        # Create observe trace
        await _eval_gate(client, agent["id"], "rbac")

        # Promote to warn
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")

        # Create warn trace
        await _eval_gate(client, agent["id"], "injection")

        # Check both traces exist with their respective modes
        resp = await client.get(f"/v1/agents/{agent['id']}/traces")
        traces = resp.json()
        modes = {t["rollout_mode"] for t in traces}
        assert "observe" in modes
        assert "warn" in modes


# ═══════════════════════════════════════════════════════════════════════
# 31e — Promotion readiness (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestPromotionReadiness:
    """31e — Promotion readiness check."""

    async def test_readiness_observe_mode(self, client: AsyncClient):
        """Readiness in observe: can_promote_to=['warn'] if validated, else blocker."""
        agent = await _create_agent(client)

        # No validation yet — blocker
        resp = await client.get(f"/v1/agents/{agent['id']}/rollout/readiness")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_mode"] == "observe"
        assert len(data["blockers"]) > 0

        # Add validation
        await _inject_validation_run(agent["id"], 10, 12)
        resp = await client.get(f"/v1/agents/{agent['id']}/rollout/readiness")
        data = resp.json()
        assert "warn" in data["can_promote_to"]
        assert len(data["blockers"]) == 0

    async def test_readiness_warn_mode_100pc(self, client: AsyncClient):
        """Readiness in warn with 100% → can_promote_to=['enforce']."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)
        await _promote(client, agent["id"], "warn")

        resp = await client.get(f"/v1/agents/{agent['id']}/rollout/readiness")
        data = resp.json()
        assert data["current_mode"] == "warn"
        assert "enforce" in data["can_promote_to"]
        assert len(data["blockers"]) == 0

    async def test_readiness_warn_mode_low_score(self, client: AsyncClient):
        """Readiness in warn with low score → blocker with score info."""
        agent = await _create_agent(client)
        await _inject_validation_run(agent["id"], 12, 12)  # needed to promote
        await _promote(client, agent["id"], "warn")
        # Inject a newer low-score run
        await _inject_validation_run(agent["id"], 10, 12)

        resp = await client.get(f"/v1/agents/{agent['id']}/rollout/readiness")
        data = resp.json()
        assert data["current_mode"] == "warn"
        assert len(data["can_promote_to"]) == 0
        assert len(data["blockers"]) > 0
        assert "10/12" in data["blockers"][0]

    async def test_readiness_stats_computed(self, client: AsyncClient):
        """Stats: traces_in_current_mode + would_have_blocked correct."""
        agent = await _create_agent(client)

        # Generate some traces in observe
        await _eval_gate(client, agent["id"], "rbac")  # deny → not enforced
        await _eval_gate(client, agent["id"], "injection")  # block → not enforced
        await _eval_gate(client, agent["id"], "pii")  # redact → not enforced

        resp = await client.get(f"/v1/agents/{agent['id']}/rollout/readiness")
        data = resp.json()
        stats = data["stats"]
        assert stats["traces_in_current_mode"] == 3
        assert stats["would_have_blocked"] == 3  # all deny/block/redact not enforced
