"""Tests for Traces & Incidents — spec 32 (50 tests).

Covers:
  32a — Trace DB model (10 tests)
  32b — Incident model (10 tests)
  32c — Trace recording service (12 tests)
  32d — Traces API (12 tests)
  32e — Trace statistics (6 tests)
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from src.db.session import async_session
from src.main import app
from src.wizard.models import (
    AgentIncident,
    AgentTrace,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    RolloutMode,
    TraceDecision,
    TraceGate,
)
from src.wizard.services.trace_recorder import TraceRecorder, compute_severity


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Helpers ──────────────────────────────────────────────────────────

_AGENT_BODY = {
    "name": "TraceTestAgent",
    "description": "Agent for trace tests",
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
    body = {**_AGENT_BODY, "name": f"TraceAgent-{uuid.uuid4().hex[:8]}", **overrides}
    resp = await client.post("/v1/agents", json=body)
    assert resp.status_code == 201
    return resp.json()


def _trace_body(
    *,
    gate: str = "pre_tool",
    decision: str = "ALLOW",
    category: str = "policy",
    session_id: str = "sess-1",
    rollout_mode: str = "observe",
    enforced: bool = False,
    latency_ms: int = 3,
    tool_name: str | None = "search_db",
    role: str | None = "viewer",
    reason: str = "allowed by policy",
    details: dict | None = None,
) -> dict:
    return {
        "gate": gate,
        "decision": decision,
        "category": category,
        "session_id": session_id,
        "rollout_mode": rollout_mode,
        "enforced": enforced,
        "latency_ms": latency_ms,
        "tool_name": tool_name,
        "role": role,
        "reason": reason,
        "details": details,
    }


async def _record_trace(client: AsyncClient, agent_id: str, **kw) -> dict:
    body = _trace_body(**kw)
    resp = await client.post(f"/v1/agents/{agent_id}/traces/record", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _record_via_service(agent_id: str, **kw) -> AgentTrace:
    """Record trace directly via TraceRecorder (no HTTP)."""
    async with async_session() as db:
        recorder = TraceRecorder(db)
        defaults = {
            "agent_id": uuid.UUID(agent_id),
            "gate": TraceGate.PRE_TOOL,
            "decision": TraceDecision.DENY,
            "category": "rbac",
            "rollout_mode": RolloutMode.OBSERVE,
            "enforced": False,
            "reason": "rbac violation",
        }
        defaults.update(kw)
        return await recorder.record(**defaults)


# ═══════════════════════════════════════════════════════════════════════
# 32a — Trace DB model (10 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestTraceModel:
    """32a — Trace DB model."""

    async def test_create_trace(self, client: AsyncClient):
        """Insert trace, all fields persisted."""
        agent = await _create_agent(client)
        trace = await _record_trace(
            client,
            agent["id"],
            gate="pre_tool",
            decision="DENY",
            category="rbac",
            tool_name="admin_panel",
            role="viewer",
            reason="not allowed",
            details={"matched_rule": "deny_admin"},
        )
        assert trace["gate"] == "pre_tool"
        assert trace["decision"] == "DENY"
        assert trace["category"] == "rbac"
        assert trace["tool_name"] == "admin_panel"
        assert trace["role"] == "viewer"
        assert trace["reason"] == "not allowed"
        assert trace["details"] == {"matched_rule": "deny_admin"}

    async def test_trace_uuid_auto_generated(self, client: AsyncClient):
        """id is UUID, auto-set."""
        agent = await _create_agent(client)
        trace = await _record_trace(client, agent["id"])
        assert trace["id"] is not None
        uuid.UUID(trace["id"])  # validates format

    async def test_trace_timestamp_auto_set(self, client: AsyncClient):
        """timestamp defaults to now."""
        agent = await _create_agent(client)
        trace = await _record_trace(client, agent["id"])
        assert trace["timestamp"] is not None
        ts = datetime.fromisoformat(trace["timestamp"])
        assert (datetime.now(UTC) - ts).total_seconds() < 60

    async def test_trace_fk_agent(self, client: AsyncClient):
        """agent_id must reference existing agent."""
        fake_id = str(uuid.uuid4())
        body = _trace_body()
        resp = await client.post(f"/v1/agents/{fake_id}/traces/record", json=body)
        assert resp.status_code == 404

    async def test_trace_gate_values(self):
        """TraceGate has pre_tool/post_tool/pre_llm/post_llm."""
        assert set(g.value for g in TraceGate) == {"pre_tool", "post_tool", "pre_llm", "post_llm"}

    async def test_trace_decision_values(self):
        """TraceDecision has ALLOW/DENY/REDACT/WARN."""
        assert set(d.value for d in TraceDecision) == {"ALLOW", "DENY", "REDACT", "WARN"}

    async def test_trace_details_jsonb(self, client: AsyncClient):
        """details field stores and retrieves complex JSON."""
        agent = await _create_agent(client)
        complex_details = {
            "input_snippet": "DROP TABLE users",
            "patterns": [{"name": "sql_injection", "score": 0.95}],
            "nested": {"a": {"b": [1, 2, 3]}},
        }
        trace = await _record_trace(client, agent["id"], details=complex_details)
        assert trace["details"] == complex_details

    async def test_trace_index_agent_timestamp(self, client: AsyncClient):
        """Query by agent_id + timestamp range works (index exists)."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"])
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/list")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_trace_index_agent_session(self, client: AsyncClient):
        """Query by agent_id + session_id works."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], session_id="unique-sess-123")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/list?session_id=unique-sess-123")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_trace_rollout_mode_stored(self, client: AsyncClient):
        """rollout_mode persisted correctly."""
        agent = await _create_agent(client)
        trace = await _record_trace(client, agent["id"], rollout_mode="warn", enforced=False)
        assert trace["rollout_mode"] == "warn"
        assert trace["enforced"] is False


# ═══════════════════════════════════════════════════════════════════════
# 32b — Incident model (10 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestIncidentModel:
    """32b — Incident model."""

    async def test_create_incident(self, client: AsyncClient):
        """Insert incident via trace, all fields persisted."""
        agent = await _create_agent(client)
        trace = await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        assert trace["incident_id"] is not None
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents")
        incidents = resp.json()["items"]
        assert len(incidents) >= 1
        inc = incidents[0]
        assert inc["severity"] in ["low", "medium", "high", "critical"]
        assert inc["status"] == "open"

    async def test_incident_severity_values(self):
        """IncidentSeverity has low/medium/high/critical."""
        assert set(s.value for s in IncidentSeverity) == {"low", "medium", "high", "critical"}

    async def test_incident_status_values(self):
        """IncidentStatus has open/acknowledged/resolved/false_positive."""
        assert set(s.value for s in IncidentStatus) == {"open", "acknowledged", "resolved", "false_positive"}

    async def test_incident_default_status(self, client: AsyncClient):
        """New incident → status=open."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents")
        assert resp.json()["items"][0]["status"] == "open"

    async def test_incident_trace_count(self, client: AsyncClient):
        """trace_count matches linked traces."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents")
        inc = resp.json()["items"][0]
        assert inc["trace_count"] == 3

    async def test_incident_fk_agent(self, client: AsyncClient):
        """Incident references correct agent."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents")
        inc = resp.json()["items"][0]
        assert inc["agent_id"] == agent["id"]

    async def test_trace_incident_fk(self, client: AsyncClient):
        """trace.incident_id references incident."""
        agent = await _create_agent(client)
        trace = await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        assert trace["incident_id"] is not None
        # Verify the incident exists
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents")
        inc_ids = {i["id"] for i in resp.json()["items"]}
        assert trace["incident_id"] in inc_ids

    async def test_severity_rbac_enforce(self):
        """RBAC violation in enforce → severity=HIGH."""
        sev = compute_severity("rbac", TraceDecision.DENY, RolloutMode.ENFORCE)
        assert sev == IncidentSeverity.HIGH

    async def test_severity_injection(self):
        """Injection detected → severity=CRITICAL."""
        sev = compute_severity("injection", TraceDecision.DENY, RolloutMode.ENFORCE)
        assert sev == IncidentSeverity.CRITICAL

    async def test_severity_observe_mode(self):
        """Any decision in observe → severity=LOW."""
        sev = compute_severity("rbac", TraceDecision.DENY, RolloutMode.OBSERVE)
        assert sev == IncidentSeverity.LOW
        sev2 = compute_severity("injection", TraceDecision.DENY, RolloutMode.OBSERVE)
        assert sev2 == IncidentSeverity.LOW


# ═══════════════════════════════════════════════════════════════════════
# 32c — Trace recording service (12 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestTraceRecorder:
    """32c — Trace recording service."""

    async def test_record_allow_no_incident(self, client: AsyncClient):
        """ALLOW decision → trace created, no incident."""
        agent = await _create_agent(client)
        trace = await _record_trace(client, agent["id"], decision="ALLOW", category="policy")
        assert trace["incident_id"] is None

    async def test_record_deny_creates_incident(self, client: AsyncClient):
        """DENY decision → trace + incident created."""
        agent = await _create_agent(client)
        trace = await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        assert trace["incident_id"] is not None

    async def test_record_redact_creates_incident(self, client: AsyncClient):
        """REDACT decision → trace + incident created."""
        agent = await _create_agent(client)
        trace = await _record_trace(client, agent["id"], decision="REDACT", category="pii")
        assert trace["incident_id"] is not None

    async def test_record_warn_creates_incident(self, client: AsyncClient):
        """WARN decision → trace + incident (low severity)."""
        agent = await _create_agent(client)
        trace = await _record_trace(
            client,
            agent["id"],
            decision="WARN",
            category="rbac",
            rollout_mode="warn",
        )
        assert trace["incident_id"] is not None
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents")
        inc = resp.json()["items"][0]
        assert inc["severity"] == "low"  # warn mode → always low

    async def test_incident_dedup_same_category_1h(self, client: AsyncClient):
        """3 DENY+rbac within 1h → 1 incident, 3 traces linked."""
        agent = await _create_agent(client)
        for _ in range(3):
            await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents?category=rbac_violation")
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["trace_count"] == 3

    async def test_incident_dedup_different_category(self, client: AsyncClient):
        """DENY+rbac + DENY+injection within 1h → 2 incidents."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        await _record_trace(client, agent["id"], decision="DENY", category="injection")
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents")
        assert resp.json()["total"] >= 2

    async def test_incident_dedup_same_category_2h(self, client: AsyncClient):
        """2 DENY+rbac 2h apart → 2 separate incidents."""
        agent = await _create_agent(client)
        aid = uuid.UUID(agent["id"])

        async with async_session() as db:
            recorder = TraceRecorder(db)
            # First trace: now - 3 hours
            t1 = AgentTrace(
                agent_id=aid,
                session_id="s1",
                timestamp=datetime.now(UTC) - timedelta(hours=3),
                gate=TraceGate.PRE_TOOL,
                decision=TraceDecision.DENY,
                reason="test",
                category="rbac",
                rollout_mode=RolloutMode.OBSERVE,
                enforced=False,
                latency_ms=1,
            )
            # Create first incident
            inc1 = AgentIncident(
                agent_id=aid,
                severity=IncidentSeverity.LOW,
                category=IncidentCategory.RBAC_VIOLATION,
                title="RBAC old",
                status=IncidentStatus.OPEN,
                first_seen=datetime.now(UTC) - timedelta(hours=3),
                last_seen=datetime.now(UTC) - timedelta(hours=3),
                trace_count=1,
            )
            db.add(inc1)
            await db.flush()
            t1.incident_id = inc1.id
            db.add(t1)
            await db.commit()

            # Second trace: now (should create new incident since > 1h gap)
            t2 = await recorder.record(
                agent_id=aid,
                gate=TraceGate.PRE_TOOL,
                decision=TraceDecision.DENY,
                category="rbac",
                rollout_mode=RolloutMode.OBSERVE,
                enforced=False,
                reason="test 2",
            )
            assert t2.incident_id != inc1.id

    async def test_incident_last_seen_updated(self, client: AsyncClient):
        """Second trace in incident → last_seen updated."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        resp1 = await client.get(f"/v1/agents/{agent['id']}/incidents")
        last1 = resp1.json()["items"][0]["last_seen"]

        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        resp2 = await client.get(f"/v1/agents/{agent['id']}/incidents")
        last2 = resp2.json()["items"][0]["last_seen"]

        assert last2 >= last1

    async def test_incident_trace_count_incremented(self, client: AsyncClient):
        """3 traces → incident.trace_count=3."""
        agent = await _create_agent(client)
        for _ in range(3):
            await _record_trace(client, agent["id"], decision="DENY", category="pii")
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents")
        inc = resp.json()["items"][0]
        assert inc["trace_count"] == 3

    async def test_recorder_async(self, client: AsyncClient):
        """record() is async, works with async DB session."""
        agent = await _create_agent(client)
        trace = await _record_via_service(agent["id"])
        assert trace.id is not None
        assert trace.decision == TraceDecision.DENY

    async def test_recorder_concurrent_safety(self, client: AsyncClient):
        """10 concurrent record() calls → no race conditions."""
        agent = await _create_agent(client)
        aid = agent["id"]

        async def record_one(i: int):
            return await _record_trace(
                client,
                aid,
                decision="DENY",
                category="rbac",
                session_id=f"sess-{i}",
            )

        results = await asyncio.gather(*[record_one(i) for i in range(10)])
        assert len(results) == 10
        assert all(r["id"] is not None for r in results)

    async def test_recorder_incident_title_generated(self, client: AsyncClient):
        """Title includes category + context."""
        agent = await _create_agent(client)
        await _record_trace(
            client,
            agent["id"],
            decision="DENY",
            category="rbac",
            role="viewer",
            tool_name="admin_panel",
            reason="viewer cannot access admin_panel",
        )
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents")
        inc = resp.json()["items"][0]
        title = inc["title"]
        assert "Rbac" in title or "rbac" in title.lower()


# ═══════════════════════════════════════════════════════════════════════
# 32d — Traces API (12 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestTracesAPI:
    """32d — Traces API."""

    async def test_get_traces_list(self, client: AsyncClient):
        """GET /agents/:id/traces/list → paginated list."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"])
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert data["total"] >= 1

    async def test_get_traces_filter_gate(self, client: AsyncClient):
        """?gate=pre_tool → only pre_tool traces."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], gate="pre_tool")
        await _record_trace(client, agent["id"], gate="post_tool")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/list?gate=pre_tool")
        items = resp.json()["items"]
        assert all(t["gate"] == "pre_tool" for t in items)

    async def test_get_traces_filter_decision(self, client: AsyncClient):
        """?decision=DENY → only DENY traces."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        await _record_trace(client, agent["id"], decision="ALLOW")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/list?decision=DENY")
        items = resp.json()["items"]
        assert len(items) >= 1
        assert all(t["decision"] == "DENY" for t in items)

    async def test_get_traces_filter_category(self, client: AsyncClient):
        """?category=rbac → only rbac traces."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], category="rbac", decision="DENY")
        await _record_trace(client, agent["id"], category="injection", decision="DENY")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/list?category=rbac")
        items = resp.json()["items"]
        assert all(t["category"] == "rbac" for t in items)

    async def test_get_traces_filter_rollout_mode(self, client: AsyncClient):
        """?rollout_mode=observe → only observe traces."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], rollout_mode="observe")
        await _record_trace(client, agent["id"], rollout_mode="warn")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/list?rollout_mode=observe")
        items = resp.json()["items"]
        assert all(t["rollout_mode"] == "observe" for t in items)

    async def test_get_traces_filter_session(self, client: AsyncClient):
        """?session_id=abc → only that session."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], session_id="abc")
        await _record_trace(client, agent["id"], session_id="xyz")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/list?session_id=abc")
        items = resp.json()["items"]
        assert all(t["session_id"] == "abc" for t in items)

    async def test_get_traces_filter_time_range(self, client: AsyncClient):
        """?from=...&to=... → only traces in range."""
        agent = await _create_agent(client)
        # Create a trace now
        await _record_trace(client, agent["id"])
        # Query future range — should return 0
        future = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = await client.get(
            f"/v1/agents/{agent['id']}/traces/list",
            params={"from": future},
        )
        assert resp.json()["total"] == 0

    async def test_get_traces_pagination(self, client: AsyncClient):
        """Create 60 traces, page=2&per_page=50 → 10 items, total=60."""
        agent = await _create_agent(client)
        for i in range(60):
            await _record_trace(client, agent["id"], session_id=f"bulk-{i}")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/list?page=2&per_page=50")
        data = resp.json()
        assert data["total"] == 60
        assert len(data["items"]) == 10
        assert data["page"] == 2

    async def test_get_incidents_list(self, client: AsyncClient):
        """GET /agents/:id/incidents → list."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents")
        assert resp.status_code == 200
        assert "items" in resp.json()
        assert resp.json()["total"] >= 1

    async def test_get_incidents_filter_status(self, client: AsyncClient):
        """?status=open → only open incidents."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents?status=open")
        items = resp.json()["items"]
        assert all(i["status"] == "open" for i in items)

    async def test_get_incidents_filter_severity(self, client: AsyncClient):
        """?severity=low → only low severity."""
        agent = await _create_agent(client)
        # observe mode → severity LOW
        await _record_trace(
            client,
            agent["id"],
            decision="DENY",
            category="rbac",
            rollout_mode="observe",
        )
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents?severity=low")
        items = resp.json()["items"]
        assert all(i["severity"] == "low" for i in items)

    async def test_patch_incident_status(self, client: AsyncClient):
        """PATCH status=resolved → 200, status updated."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents")
        inc_id = resp.json()["items"][0]["id"]

        resp = await client.patch(
            f"/v1/agents/{agent['id']}/incidents/{inc_id}",
            json={"status": "resolved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"


# ═══════════════════════════════════════════════════════════════════════
# 32e — Trace statistics (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestTraceStats:
    """32e — Trace statistics endpoint."""

    async def test_stats_total_evaluations(self, client: AsyncClient):
        """stats.total_evaluations matches trace count."""
        agent = await _create_agent(client)
        for _ in range(5):
            await _record_trace(client, agent["id"])
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/stats")
        assert resp.status_code == 200
        assert resp.json()["total_evaluations"] == 5

    async def test_stats_by_decision(self, client: AsyncClient):
        """by_decision breakdown matches actual."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], decision="ALLOW")
        await _record_trace(client, agent["id"], decision="ALLOW")
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/stats")
        by_decision = resp.json()["by_decision"]
        assert by_decision.get("ALLOW") == 2
        assert by_decision.get("DENY") == 1

    async def test_stats_by_category(self, client: AsyncClient):
        """by_category breakdown matches actual."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], category="rbac", decision="DENY")
        await _record_trace(client, agent["id"], category="rbac", decision="DENY")
        await _record_trace(client, agent["id"], category="injection", decision="DENY")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/stats")
        by_cat = resp.json()["by_category"]
        assert by_cat.get("rbac") == 2
        assert by_cat.get("injection") == 1

    async def test_stats_by_gate(self, client: AsyncClient):
        """by_gate breakdown matches actual."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"], gate="pre_tool")
        await _record_trace(client, agent["id"], gate="pre_tool")
        await _record_trace(client, agent["id"], gate="post_tool")
        resp = await client.get(f"/v1/agents/{agent['id']}/traces/stats")
        by_gate = resp.json()["by_gate"]
        assert by_gate.get("pre_tool") == 2
        assert by_gate.get("post_tool") == 1

    async def test_stats_time_range_filter(self, client: AsyncClient):
        """Stats with date range → only counts traces in range."""
        agent = await _create_agent(client)
        await _record_trace(client, agent["id"])
        # Query future range → 0
        future = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = await client.get(
            f"/v1/agents/{agent['id']}/traces/stats",
            params={"from": future},
        )
        assert resp.json()["total_evaluations"] == 0

    async def test_stats_incidents_count(self, client: AsyncClient):
        """incidents.open/resolved match actual."""
        agent = await _create_agent(client)
        # Create 2 incidents
        await _record_trace(client, agent["id"], decision="DENY", category="rbac")
        await _record_trace(client, agent["id"], decision="DENY", category="injection")

        # Resolve one
        resp = await client.get(f"/v1/agents/{agent['id']}/incidents")
        inc_id = resp.json()["items"][0]["id"]
        await client.patch(
            f"/v1/agents/{agent['id']}/incidents/{inc_id}",
            json={"status": "resolved"},
        )

        resp = await client.get(f"/v1/agents/{agent['id']}/traces/stats")
        inc = resp.json()["incidents"]
        assert inc["open"] == 1
        assert inc["resolved"] == 1
