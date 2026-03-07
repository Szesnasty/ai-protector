"""Tests for Agent Trace — spec 07 (Phase 1: in-memory trace).

Covers:
- TraceAccumulator lifecycle (start → record → finalize → to_dict)
- Intent recording
- Iteration management (auto-start, multiple iterations)
- Tool plan recording
- Pre-tool gate decision recording (ALLOW / BLOCK with counters)
- Tool execution recording (result_preview truncation, counters)
- Post-tool gate decision recording
- LLM call recording (token counters)
- Limit tracking
- Node timing
- Finalize (duration, counters, errors, node_timings)
- Integration: trace flows through all graph nodes
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from src.agent.trace.accumulator import TraceAccumulator

# ── Unit: TraceAccumulator ────────────────────────────────────────────


class TestTraceAccumulatorLifecycle:
    """Basic lifecycle: create → start → to_dict."""

    def test_fresh_accumulator_empty(self):
        t = TraceAccumulator()
        assert t.to_dict() == {}
        assert t.data == {}

    def test_start_populates_trace(self):
        t = TraceAccumulator()
        t.start(session_id="s1", user_role="admin", model="m1", user_message="hi")
        d = t.to_dict()
        assert d["session_id"] == "s1"
        assert d["user_role"] == "admin"
        assert d["model"] == "m1"
        assert d["user_message"] == "hi"
        assert d["trace_id"]  # UUID
        assert d["timestamp"]
        assert d["iterations"] == []
        assert d["counters"]["iterations"] == 0

    def test_wrap_existing_dict(self):
        data = {"trace_id": "existing", "intent": "order_query"}
        t = TraceAccumulator(data)
        assert t.data is data  # Same reference
        assert t.to_dict()["trace_id"] == "existing"


class TestTraceIntent:
    def test_record_intent(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.record_intent("order_query", 0.92)
        assert t.data["intent"] == "order_query"
        assert t.data["intent_confidence"] == 0.92


class TestTraceIterations:
    def test_start_iteration_creates_iteration(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        assert len(t.data["iterations"]) == 1
        it = t.data["iterations"][0]
        assert it["iteration"] == 1
        assert it["tool_plan"] == []
        assert it["pre_tool_decisions"] == []
        assert it["tool_executions"] == []
        assert it["post_tool_decisions"] == []
        assert it["llm_call"] is None
        assert it["firewall_decision"] is None

    def test_multiple_iterations(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        t.start_iteration()
        t.start_iteration()
        assert len(t.data["iterations"]) == 3
        assert t.data["iterations"][2]["iteration"] == 3

    def test_auto_start_iteration_on_record(self):
        """If no iteration exists, recording auto-starts one."""
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.record_tool_plan([{"tool": "foo", "args": {}}])
        assert len(t.data["iterations"]) == 1


class TestTraceToolPlan:
    def test_record_tool_plan(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        t.record_tool_plan(
            [
                {"tool": "getOrderStatus", "args": {"order_id": "ORD-123"}},
                {"tool": "searchKnowledgeBase", "args": {"query": "refund"}},
            ]
        )
        plans = t.data["iterations"][0]["tool_plan"]
        assert len(plans) == 2
        assert plans[0]["tool"] == "getOrderStatus"
        assert plans[1]["args"] == {"query": "refund"}


class TestTracePreToolDecision:
    def test_allow_decision(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        t.record_pre_tool_decision(
            tool="getOrderStatus",
            decision="ALLOW",
            reason=None,
            checks=[{"check": "rbac", "passed": True, "detail": None}],
            risk_score=0.0,
        )
        decs = t.data["iterations"][0]["pre_tool_decisions"]
        assert len(decs) == 1
        assert decs[0]["decision"] == "ALLOW"
        assert t.data["counters"]["tool_calls_blocked"] == 0

    def test_block_increments_counter(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        t.record_pre_tool_decision(
            tool="getInternalSecrets",
            decision="BLOCK",
            reason="Not permitted",
            checks=[{"check": "rbac", "passed": False, "detail": "denied"}],
            risk_score=1.0,
        )
        assert t.data["counters"]["tool_calls_blocked"] == 1
        # Block again
        t.record_pre_tool_decision(
            tool="deleteAll",
            decision="BLOCK",
            reason="No way",
            checks=[],
            risk_score=1.0,
        )
        assert t.data["counters"]["tool_calls_blocked"] == 2


class TestTraceToolExecution:
    def test_record_execution(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        t.record_tool_execution(
            tool="getOrderStatus",
            args={"order_id": "ORD-123"},
            result='{"status": "shipped"}',
            duration_ms=42,
        )
        execs = t.data["iterations"][0]["tool_executions"]
        assert len(execs) == 1
        assert execs[0]["tool"] == "getOrderStatus"
        assert execs[0]["duration_ms"] == 42
        assert t.data["counters"]["tool_calls"] == 1

    def test_result_preview_truncated(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        long_result = "x" * 500
        t.record_tool_execution("foo", {}, long_result, 10)
        ex = t.data["iterations"][0]["tool_executions"][0]
        assert len(ex["result_preview"]) == 200
        assert ex["result_length"] == 500


class TestTracePostToolDecision:
    def test_record_post_decision(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        t.record_post_tool_decision(
            tool="getOrderStatus",
            decision="REDACT",
            pii_count=2,
            secrets_count=0,
            injection_score=0.0,
            reason="Redacted: 2 PII entities",
        )
        posts = t.data["iterations"][0]["post_tool_decisions"]
        assert len(posts) == 1
        assert posts[0]["pii_count"] == 2
        assert posts[0]["decision"] == "REDACT"


class TestTraceLLMCall:
    def test_record_llm_call(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        t.record_llm_call(
            messages_count=5,
            tokens_in=100,
            tokens_out=50,
            duration_ms=1200,
            firewall={"decision": "ALLOW", "risk_score": 0.1},
        )
        it = t.data["iterations"][0]
        assert it["llm_call"]["tokens_in"] == 100
        assert it["llm_call"]["tokens_out"] == 50
        assert it["llm_call"]["duration_ms"] == 1200
        assert it["firewall_decision"]["decision"] == "ALLOW"
        assert t.data["counters"]["tokens_in"] == 100
        assert t.data["counters"]["tokens_out"] == 50

    def test_multiple_llm_calls_accumulate_tokens(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        t.record_llm_call(tokens_in=100, tokens_out=50)
        t.start_iteration()
        t.record_llm_call(tokens_in=200, tokens_out=80)
        assert t.data["counters"]["tokens_in"] == 300
        assert t.data["counters"]["tokens_out"] == 130


class TestTraceLimits:
    def test_record_limit_hit(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.record_limit_hit("session_max_turns")
        assert t.data["limits_hit"] == "session_max_turns"


class TestTraceNodeTiming:
    def test_record_node_timing(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.record_node_timing("input_node", 5.2)
        t.record_node_timing("intent_node", 1.1)
        assert t.data["node_timings"]["input_node"] == 5.2
        assert t.data["node_timings"]["intent_node"] == 1.1


class TestTraceFinalize:
    def test_finalize_sets_duration_and_counters(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        t.record_llm_call(tokens_in=10, tokens_out=5)
        time.sleep(0.01)  # Ensure >0 ms
        t.finalize(final_response="Done.", errors=["oops"])
        d = t.to_dict()
        assert d["final_response"] == "Done."
        assert d["errors"] == ["oops"]
        assert d["counters"]["iterations"] == 1
        assert d["total_duration_ms"] > 0

    def test_finalize_counters_override(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.finalize(counters_override={"estimated_cost": 0.003})
        assert t.data["counters"]["estimated_cost"] == 0.003

    def test_finalize_node_timings(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        t.finalize(node_timings={"a": 1.0, "b": 2.0})
        assert t.data["node_timings"] == {"a": 1.0, "b": 2.0}


class TestTraceToDict:
    def test_to_dict_returns_copy(self):
        t = TraceAccumulator()
        t.start(session_id="s1")
        d = t.to_dict()
        d["session_id"] = "changed"
        # Original not changed via to_dict (shallow copy of dict)
        assert t.data["session_id"] == "s1"


# ── Integration: trace flows through graph nodes ──────────────────────


class TestNodeTraceIntegration:
    """Verify each node propagates trace correctly."""

    def _base_state(self) -> dict:
        """Return a minimal agent state with no trace yet."""
        return {
            "session_id": "test-session-1",
            "user_role": "customer",
            "message": "Where is my order ORD-123?",
            "policy": "default",
            "model": "qwen",
            "api_key": None,
        }

    @patch("src.agent.nodes.input.session_store")
    @patch("src.agent.nodes.input.get_limits_service")
    def test_input_node_starts_trace(self, mock_limits_svc, mock_store):
        from src.agent.nodes.input import input_node

        mock_store.get_history.return_value = []
        limits = MagicMock()
        limits.check_request_entry.return_value = MagicMock(allowed=True)
        limits.get_session_usage.return_value = {
            "session_tool_calls": 0,
            "session_tokens_in": 0,
            "session_tokens_out": 0,
            "session_estimated_cost": 0.0,
            "session_turns": 0,
        }
        mock_limits_svc.return_value = limits

        result = input_node(self._base_state())
        trace = result["trace"]
        assert trace["session_id"] == "test-session-1"
        assert trace["trace_id"]
        assert trace["user_role"] == "customer"
        assert trace["model"] == "qwen"

    def test_intent_node_records_intent(self):
        from src.agent.nodes.intent import intent_node

        t = TraceAccumulator()
        t.start(session_id="s1")
        state = {**self._base_state(), "trace": t.data}

        result = intent_node(state)
        assert result["trace"]["intent"] == "order_query"
        assert result["trace"]["intent_confidence"] > 0

    @patch("src.agent.nodes.tools.execute_tool")
    def test_tool_executor_records_execution(self, mock_exec):
        from src.agent.nodes.tools import tool_executor_node

        mock_exec.return_value = '{"status": "shipped"}'

        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        state = {
            **self._base_state(),
            "allowed_tools": ["getOrderStatus"],
            "tool_plan": [{"tool": "getOrderStatus", "args": {"order_id": "ORD-123"}}],
            "tool_calls": [],
            "iterations": 0,
            "trace": t.data,
        }

        result = tool_executor_node(state)
        execs = result["trace"]["iterations"][0]["tool_executions"]
        assert len(execs) == 1
        assert execs[0]["tool"] == "getOrderStatus"
        assert result["trace"]["counters"]["tool_calls"] == 1

    @patch("src.agent.nodes.pre_tool_gate.get_rbac_service")
    @patch("src.agent.nodes.pre_tool_gate.get_limits_service")
    def test_pre_tool_gate_records_decisions(self, mock_limits, mock_rbac):
        from src.agent.nodes.pre_tool_gate import pre_tool_gate_node

        # RBAC: allow getOrderStatus
        rbac = MagicMock()
        rbac.check_permission.return_value = MagicMock(
            allowed=True,
            requires_confirmation=False,
            reason=None,
            tool_sensitivity="low",
        )
        mock_rbac.return_value = rbac

        limits = MagicMock()
        limits.check_tool_limits.return_value = MagicMock(allowed=True)
        limits.check_token_budget.return_value = MagicMock(allowed=True)
        limits.increment_tool_calls.return_value = None
        mock_limits.return_value = limits

        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        state = {
            **self._base_state(),
            "allowed_tools": ["getOrderStatus"],
            "tool_plan": [{"tool": "getOrderStatus", "args": {"order_id": "ORD-123"}}],
            "tool_calls": [],
            "iterations": 0,
            "gate_decisions": [],
            "trace": t.data,
        }

        result = pre_tool_gate_node(state)
        decs = result["trace"]["iterations"][0]["pre_tool_decisions"]
        assert len(decs) == 1
        assert decs[0]["decision"] == "ALLOW"

    def test_post_tool_gate_records_decisions(self):
        from src.agent.nodes.post_tool_gate import post_tool_gate_node

        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        state = {
            **self._base_state(),
            "tool_calls": [
                {
                    "tool": "getOrderStatus",
                    "args": {"order_id": "ORD-123"},
                    "result": '{"status": "shipped", "email": "user@test.com"}',
                    "allowed": True,
                },
            ],
            "trace": t.data,
        }

        result = post_tool_gate_node(state)
        posts = result["trace"]["iterations"][0]["post_tool_decisions"]
        assert len(posts) == 1
        # Email should cause REDACT
        assert posts[0]["decision"] == "REDACT"
        assert posts[0]["pii_count"] > 0

    @patch("src.agent.nodes.input.session_store")
    @patch("src.agent.nodes.input.get_limits_service")
    def test_input_records_limit_hit(self, mock_limits_svc, mock_store):
        from src.agent.nodes.input import input_node

        mock_store.get_history.return_value = []
        limits = MagicMock()
        limits.check_request_entry.return_value = MagicMock(
            allowed=False,
            limit_type="session_max_turns",
            message="Turn limit reached.",
        )
        limits.get_session_usage.return_value = {
            "session_tool_calls": 0,
            "session_tokens_in": 0,
            "session_tokens_out": 0,
            "session_estimated_cost": 0.0,
            "session_turns": 10,
        }
        mock_limits_svc.return_value = limits

        result = input_node(self._base_state())
        assert result["trace"]["limits_hit"] == "session_max_turns"

    def test_memory_node_finalizes_trace(self):
        from src.agent.nodes.memory import memory_node

        t = TraceAccumulator()
        t.start(session_id="s1")
        t.start_iteration()
        time.sleep(0.01)

        state = {
            "session_id": "s1",
            "message": "hello",
            "final_response": "Hi there!",
            "llm_response": "Hi there!",
            "errors": [],
            "node_timings": {"input_node": 2.0},
            "session_estimated_cost": 0.001,
            "trace": t.data,
        }

        with patch("src.agent.nodes.memory.session_store"):
            result = memory_node(state)

        trace = result["trace"]
        assert trace["final_response"] == "Hi there!"
        assert trace["total_duration_ms"] > 0
        assert trace["counters"]["iterations"] == 1
        assert trace["counters"]["estimated_cost"] == 0.001


# ── Schema integration ────────────────────────────────────────────────


class TestSchemaTraceField:
    def test_response_includes_trace_dict(self):
        from src.schemas import AgentChatResponse

        trace_data = {
            "trace_id": "abc-123",
            "session_id": "s1",
            "intent": "order_query",
        }
        resp = AgentChatResponse(
            response="Hello",
            session_id="s1",
            trace=trace_data,
        )
        assert resp.trace["trace_id"] == "abc-123"

    def test_response_trace_defaults_to_empty(self):
        from src.schemas import AgentChatResponse

        resp = AgentChatResponse(response="Hello", session_id="s1")
        assert resp.trace == {}


# ── End-to-end trace through mini graph ───────────────────────────────


class TestTraceEndToEnd:
    """Simulate a full trace lifecycle as it would flow through the graph."""

    def test_full_trace_lifecycle(self):
        # 1. Input node — start trace
        trace = TraceAccumulator()
        trace.start(
            session_id="e2e-session",
            user_role="customer",
            policy="default",
            model="qwen",
            user_message="Where is ORD-123?",
        )

        # 2. Intent node
        trace.record_intent("order_query", 0.95)

        # 3. Tool router — iteration 1
        trace.start_iteration()
        trace.record_tool_plan([{"tool": "getOrderStatus", "args": {"order_id": "ORD-123"}}])

        # 4. Pre-tool gate
        trace.record_pre_tool_decision(
            tool="getOrderStatus",
            decision="ALLOW",
            reason=None,
            checks=[
                {"check": "rbac", "passed": True, "detail": None},
                {"check": "schema", "passed": True, "detail": None},
                {"check": "context_risk", "passed": True, "detail": None},
                {"check": "limits", "passed": True, "detail": None},
                {"check": "confirmation", "passed": True, "detail": None},
            ],
        )

        # 5. Tool execution
        trace.record_tool_execution(
            tool="getOrderStatus",
            args={"order_id": "ORD-123"},
            result='{"order_id":"ORD-123","status":"shipped"}',
            duration_ms=15,
        )

        # 6. Post-tool gate
        trace.record_post_tool_decision(
            tool="getOrderStatus",
            decision="PASS",
        )

        # 7. LLM call
        trace.record_llm_call(
            messages_count=4,
            tokens_in=120,
            tokens_out=45,
            duration_ms=800,
            firewall={"decision": "ALLOW", "risk_score": 0.05},
        )

        # 8. Finalize
        trace.finalize(
            final_response="Your order ORD-123 has been shipped!",
            errors=[],
            node_timings={"input_node": 3.0, "intent_node": 1.0, "llm_call_node": 800.0},
        )

        # Verify full trace structure
        d = trace.to_dict()
        assert d["trace_id"]
        assert d["session_id"] == "e2e-session"
        assert d["intent"] == "order_query"
        assert d["intent_confidence"] == 0.95
        assert len(d["iterations"]) == 1

        it = d["iterations"][0]
        assert it["iteration"] == 1
        assert len(it["tool_plan"]) == 1
        assert len(it["pre_tool_decisions"]) == 1
        assert len(it["tool_executions"]) == 1
        assert len(it["post_tool_decisions"]) == 1
        assert it["llm_call"]["tokens_in"] == 120
        assert it["firewall_decision"]["decision"] == "ALLOW"

        assert d["counters"]["iterations"] == 1
        assert d["counters"]["tool_calls"] == 1
        assert d["counters"]["tool_calls_blocked"] == 0
        assert d["counters"]["tokens_in"] == 120
        assert d["counters"]["tokens_out"] == 45

        assert d["final_response"] == "Your order ORD-123 has been shipped!"
        assert d["total_duration_ms"] >= 0  # May be 0 if test runs sub-ms
        assert d["node_timings"]["input_node"] == 3.0
