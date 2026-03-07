"""Tests for Agent Trace — Phase 2 (store + REST) and Phase 3 (Langfuse + export).

Covers:
- TraceStore: save, get, list, filters, pagination, LRU eviction
- REST endpoints: GET /agent/traces, GET /agent/traces/{id}, GET .../export
- Langfuse integration: send_trace_to_langfuse (mocked)
- memory_node persists + sends
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.agent.trace.store import TraceStore, get_trace_store

# ── Helpers ───────────────────────────────────────────────────────────


def _make_trace(
    *,
    trace_id: str | None = None,
    session_id: str = "sess-1",
    user_role: str = "customer",
    intent: str = "order_query",
    model: str = "qwen",
    blocked: int = 0,
    fw_block: bool = False,
    timestamp: str | None = None,
    limits_hit: str | None = None,
) -> dict:
    """Create a realistic trace dict for testing."""
    iters = []
    if blocked > 0 or fw_block:
        it = {
            "iteration": 1,
            "tool_plan": [],
            "pre_tool_decisions": [],
            "tool_executions": [],
            "post_tool_decisions": [],
            "llm_call": {"tokens_in": 50, "tokens_out": 20, "duration_ms": 500, "messages_count": 3},
            "firewall_decision": {"decision": "BLOCK" if fw_block else "ALLOW", "risk_score": 0.5},
        }
        iters.append(it)
    else:
        it = {
            "iteration": 1,
            "tool_plan": [{"tool": "getOrderStatus", "args": {"order_id": "ORD-1"}}],
            "pre_tool_decisions": [{"tool": "getOrderStatus", "decision": "ALLOW"}],
            "tool_executions": [
                {"tool": "getOrderStatus", "result_preview": "{}", "duration_ms": 10, "result_length": 2}
            ],
            "post_tool_decisions": [{"tool": "getOrderStatus", "decision": "PASS"}],
            "llm_call": {"tokens_in": 100, "tokens_out": 45, "duration_ms": 800, "messages_count": 4},
            "firewall_decision": {"decision": "ALLOW", "risk_score": 0.05},
        }
        iters.append(it)

    return {
        "trace_id": trace_id or str(uuid4()),
        "session_id": session_id,
        "request_id": str(uuid4()),
        "timestamp": timestamp or datetime.now(UTC).isoformat(),
        "user_role": user_role,
        "policy": "default",
        "model": model,
        "user_message": "Where is ORD-1?",
        "intent": intent,
        "intent_confidence": 0.9,
        "iterations": iters,
        "final_response": "Your order has been shipped!",
        "total_duration_ms": 1200,
        "node_timings": {"input_node": 3.0, "llm_call_node": 800.0},
        "counters": {
            "iterations": 1,
            "tool_calls": 1,
            "tool_calls_blocked": blocked,
            "tokens_in": 100,
            "tokens_out": 45,
            "estimated_cost": 0.001,
        },
        "limits_hit": limits_hit,
        "errors": [],
    }


# ── TraceStore unit tests ─────────────────────────────────────────────


class TestTraceStore:
    def test_save_and_get(self):
        store = TraceStore()
        t = _make_trace(trace_id="t1")
        store.save(t)
        result = store.get("t1")
        assert result is not None
        assert result["trace_id"] == "t1"

    def test_get_nonexistent(self):
        store = TraceStore()
        assert store.get("nope") is None

    def test_save_without_trace_id(self):
        store = TraceStore()
        result = store.save({"no_id": True})
        assert result == ""

    def test_count(self):
        store = TraceStore()
        store.save(_make_trace(trace_id="a"))
        store.save(_make_trace(trace_id="b"))
        assert store.count() == 2

    def test_clear(self):
        store = TraceStore()
        store.save(_make_trace(trace_id="x"))
        store.clear()
        assert store.count() == 0

    def test_lru_eviction(self):
        store = TraceStore(max_traces=3)
        store.save(_make_trace(trace_id="a"))
        store.save(_make_trace(trace_id="b"))
        store.save(_make_trace(trace_id="c"))
        store.save(_make_trace(trace_id="d"))  # Evicts "a"
        assert store.get("a") is None
        assert store.get("b") is not None
        assert store.get("d") is not None
        assert store.count() == 3


class TestTraceStoreFilter:
    def _setup(self) -> TraceStore:
        store = TraceStore()
        store.save(_make_trace(trace_id="t1", session_id="s1", user_role="customer"))
        store.save(_make_trace(trace_id="t2", session_id="s1", user_role="admin"))
        store.save(_make_trace(trace_id="t3", session_id="s2", user_role="customer", blocked=2))
        store.save(_make_trace(trace_id="t4", session_id="s3", user_role="admin", fw_block=True))
        store.save(
            _make_trace(
                trace_id="t5",
                session_id="s4",
                timestamp="2026-01-01T00:00:00+00:00",
            )
        )
        return store

    def test_filter_session_id(self):
        store = self._setup()
        result = store.list(session_id="s1")
        assert result["total"] == 2

    def test_filter_user_role(self):
        store = self._setup()
        result = store.list(user_role="admin")
        assert result["total"] == 2

    def test_filter_has_blocks_true(self):
        store = self._setup()
        result = store.list(has_blocks=True)
        # t3 (tool blocked), t4 (firewall blocked)
        assert result["total"] == 2

    def test_filter_has_blocks_false(self):
        store = self._setup()
        result = store.list(has_blocks=False)
        assert result["total"] == 3  # t1, t2, t5

    def test_filter_date_from(self):
        store = self._setup()
        # t5 has timestamp 2026-01-01, all others are "now"
        result = store.list(date_from="2026-03-01T00:00:00+00:00")
        # Should exclude t5
        assert result["total"] == 4

    def test_filter_date_to(self):
        store = self._setup()
        result = store.list(date_to="2026-02-01T00:00:00+00:00")
        # Only t5 (Jan 1)
        assert result["total"] == 1

    def test_pagination(self):
        store = self._setup()
        result = store.list(limit=2, offset=0)
        assert len(result["items"]) == 2
        assert result["total"] == 5

        result2 = store.list(limit=2, offset=2)
        assert len(result2["items"]) == 2

        result3 = store.list(limit=2, offset=4)
        assert len(result3["items"]) == 1

    def test_list_returns_summaries(self):
        store = self._setup()
        result = store.list(limit=1)
        item = result["items"][0]
        assert "trace_id" in item
        assert "session_id" in item
        assert "intent" in item
        assert "total_duration_ms" in item
        # Full fields like "iterations" should NOT be in summary
        assert "iterations" not in item
        assert "user_message" not in item

    def test_newest_first(self):
        store = TraceStore()
        store.save(_make_trace(trace_id="old", timestamp="2026-01-01T00:00:00+00:00"))
        time.sleep(0.01)
        store.save(_make_trace(trace_id="new", timestamp="2026-03-05T12:00:00+00:00"))
        result = store.list()
        assert result["items"][0]["trace_id"] == "new"
        assert result["items"][1]["trace_id"] == "old"


# ── REST endpoint tests ───────────────────────────────────────────────


@pytest.fixture
def client():
    from src.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_store():
    """Clean trace store before each test."""
    store = get_trace_store()
    store.clear()
    yield
    store.clear()


class TestTracesEndpoints:
    def test_list_empty(self, client):
        resp = client.get("/agent/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_with_data(self, client):
        store = get_trace_store()
        store.save(_make_trace(trace_id="t1"))
        store.save(_make_trace(trace_id="t2"))

        resp = client.get("/agent/traces")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_list_with_session_filter(self, client):
        store = get_trace_store()
        store.save(_make_trace(trace_id="t1", session_id="s1"))
        store.save(_make_trace(trace_id="t2", session_id="s2"))

        resp = client.get("/agent/traces?session_id=s1")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_with_role_filter(self, client):
        store = get_trace_store()
        store.save(_make_trace(trace_id="t1", user_role="customer"))
        store.save(_make_trace(trace_id="t2", user_role="admin"))

        resp = client.get("/agent/traces?user_role=admin")
        assert resp.json()["total"] == 1

    def test_list_has_blocks_filter(self, client):
        store = get_trace_store()
        store.save(_make_trace(trace_id="t1"))
        store.save(_make_trace(trace_id="t2", blocked=1))

        resp = client.get("/agent/traces?has_blocks=true")
        assert resp.json()["total"] == 1

    def test_list_pagination(self, client):
        store = get_trace_store()
        for i in range(10):
            store.save(_make_trace(trace_id=f"t{i}"))

        resp = client.get("/agent/traces?limit=3&offset=0")
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["total"] == 10

    def test_get_trace_found(self, client):
        store = get_trace_store()
        store.save(_make_trace(trace_id="abc-123"))

        resp = client.get("/agent/traces/abc-123")
        assert resp.status_code == 200
        assert resp.json()["trace_id"] == "abc-123"
        # Full trace should include iterations
        assert "iterations" in resp.json()

    def test_get_trace_not_found(self, client):
        resp = client.get("/agent/traces/nonexistent")
        assert resp.status_code == 404

    def test_export_trace(self, client):
        store = get_trace_store()
        store.save(_make_trace(trace_id="exp-1", session_id="s1"))

        resp = client.get("/agent/traces/exp-1/export")
        assert resp.status_code == 200
        data = resp.json()

        # Check export structure
        assert data["trace_id"] == "exp-1"
        assert "exported_at" in data
        assert "summary" in data
        assert data["summary"]["tool_calls"] == 1
        assert data["summary"]["total_duration_ms"] == 1200
        assert "iterations" in data

    def test_export_with_blocks(self, client):
        store = get_trace_store()
        store.save(_make_trace(trace_id="exp-b", blocked=3, fw_block=True))

        resp = client.get("/agent/traces/exp-b/export")
        data = resp.json()
        # 3 tool blocks + 1 firewall block
        assert data["summary"]["blocks"] >= 3

    def test_export_not_found(self, client):
        resp = client.get("/agent/traces/nope/export")
        assert resp.status_code == 404


# ── Langfuse integration tests ────────────────────────────────────────


class TestLangfuseIntegration:
    def test_send_disabled_by_default(self):
        # Reset module state
        import src.agent.trace.langfuse as lf_mod
        from src.agent.trace.langfuse import send_trace_to_langfuse

        lf_mod._langfuse_available = None
        lf_mod._langfuse_client = None

        result = send_trace_to_langfuse(_make_trace())
        assert result is False

    @patch.dict("os.environ", {"AGENT_LANGFUSE_ENABLED": "true"})
    @patch("src.agent.trace.langfuse.Langfuse", create=True)
    def test_send_with_mock_langfuse(self, mock_langfuse_cls):
        import src.agent.trace.langfuse as lf_mod

        lf_mod._langfuse_available = None
        lf_mod._langfuse_client = None

        # Mock the Langfuse client
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_span = MagicMock()
        mock_client.trace.return_value = mock_trace
        mock_trace.span.return_value = mock_span

        # Patch _get_client to return our mock
        with patch.object(lf_mod, "_get_client", return_value=mock_client):
            trace = _make_trace(trace_id="lf-test")
            result = lf_mod.send_trace_to_langfuse(trace)

        assert result is True
        mock_client.trace.assert_called_once()
        mock_client.flush.assert_called_once()

    def test_send_handles_exception(self):
        import src.agent.trace.langfuse as lf_mod

        lf_mod._langfuse_available = None
        lf_mod._langfuse_client = None

        mock_client = MagicMock()
        mock_client.trace.side_effect = Exception("connection failed")

        with patch.object(lf_mod, "_get_client", return_value=mock_client):
            result = lf_mod.send_trace_to_langfuse(_make_trace())

        assert result is False


# ── memory_node integration ───────────────────────────────────────────


class TestMemoryNodePersistence:
    def test_memory_node_saves_to_store(self):
        from src.agent.nodes.memory import memory_node
        from src.agent.trace.accumulator import TraceAccumulator

        store = get_trace_store()
        store.clear()

        t = TraceAccumulator()
        t.start(session_id="mem-test")
        t.record_intent("greeting", 0.9)

        state = {
            "session_id": "mem-test",
            "message": "hello",
            "final_response": "Hi there!",
            "llm_response": "Hi there!",
            "errors": [],
            "node_timings": {},
            "session_estimated_cost": 0.0,
            "trace": t.data,
        }

        with patch("src.agent.nodes.memory.session_store"):
            with patch("src.agent.nodes.memory.send_trace_to_langfuse"):
                result = memory_node(state)

        # Should be in store
        assert store.count() >= 1
        trace_id = result["trace"].get("trace_id")
        assert trace_id
        stored = store.get(trace_id)
        assert stored is not None
        assert stored["session_id"] == "mem-test"
