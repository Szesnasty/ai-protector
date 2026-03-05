# 07 — Agent Trace: Implementation Notes

**Phase:** 1 — In-memory trace + API response  
**Status:** ✅ Complete  
**Tests:** 31 new tests in `tests/test_trace.py` (385 total all passing)

---

## What Was Implemented

### TraceAccumulator (`src/agent/trace/accumulator.py`)

A lightweight class that wraps a plain `dict` stored in `AgentState["trace"]`.
Each graph node creates `TraceAccumulator(state.get("trace"))`, calls the
appropriate `record_*` methods, then returns `{**state, "trace": trace.data}`.

Key design decisions:
- **Dict-based storage:** The trace lives as a plain dict in `AgentState` so it flows
  naturally through LangGraph's state merging. No custom serialization needed.
- **Internal state restoration:** The constructor rebuilds `_current_iteration` and
  `_iteration_count` from the existing dict, so each node's fresh `TraceAccumulator`
  instance picks up where the previous node left off.
- **`_perf_start` stored in dict:** `time.perf_counter()` timestamp is stored in the
  dict under key `_perf_start` so `finalize()` can compute `total_duration_ms` even
  when called from a different `TraceAccumulator` instance. Stripped from `to_dict()`.

### Methods

| Method | Called In | Records |
|--------|-----------|---------|
| `start()` | `input_node` | trace_id, session_id, user_role, policy, model, message, timestamp |
| `record_intent()` | `intent_node` | intent, confidence |
| `start_iteration()` | `tool_router_node` | new iteration object |
| `record_tool_plan()` | `tool_router_node` | planned tools + args |
| `record_pre_tool_decision()` | `pre_tool_gate_node` | per-tool ALLOW/BLOCK decision, checks, risk_score |
| `record_tool_execution()` | `tool_executor_node` | tool, args, result_preview (200 chars), duration_ms |
| `record_post_tool_decision()` | `post_tool_gate_node` | per-tool PASS/REDACT/BLOCK, pii_count, secrets_count |
| `record_llm_call()` | `llm_call_node` | messages_count, tokens_in/out, duration_ms, firewall verdict |
| `record_limit_hit()` | `input_node` | which limit was hit |
| `finalize()` | `memory_node` | final_response, errors, node_timings, duration, iteration count |

### Files Modified

| File | Change |
|------|--------|
| `src/agent/trace/__init__.py` | New module, exports `TraceAccumulator` |
| `src/agent/trace/accumulator.py` | New — `TraceAccumulator` class (220 lines) |
| `src/agent/state.py` | Added `trace: dict[str, Any]` field to `AgentState` |
| `src/agent/nodes/input.py` | Import + `trace.start()` + `trace.record_limit_hit()` |
| `src/agent/nodes/intent.py` | Import + `trace.record_intent()` |
| `src/agent/nodes/tools.py` | Import + `trace.start_iteration()`, `record_tool_plan()`, `record_tool_execution()` |
| `src/agent/nodes/pre_tool_gate.py` | Import + `trace.record_pre_tool_decision()` per tool |
| `src/agent/nodes/post_tool_gate.py` | Import + `trace.record_post_tool_decision()` per tool |
| `src/agent/nodes/llm_call.py` | Import + `trace.record_llm_call()` in all paths (success, 403, error) |
| `src/agent/nodes/response.py` | Import added (trace imported but not mutated here) |
| `src/agent/nodes/memory.py` | Import + `trace.finalize()` |
| `src/schemas.py` | Added `trace: dict` field to `AgentChatResponse` |
| `src/routers/chat.py` | Passes `result.get("trace", {})` to response |

### Trace Structure (example)

```json
{
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": "sess-abc",
  "timestamp": "2025-01-15T10:30:00.123456+00:00",
  "user_role": "customer",
  "policy": "default",
  "model": "qwen",
  "user_message": "Where is my order ORD-123?",
  "intent": "order_query",
  "intent_confidence": 0.95,
  "iterations": [
    {
      "iteration": 1,
      "tool_plan": [{"tool": "getOrderStatus", "args": {"order_id": "ORD-123"}}],
      "pre_tool_decisions": [{"tool": "getOrderStatus", "decision": "ALLOW", ...}],
      "tool_executions": [{"tool": "getOrderStatus", "duration_ms": 15, ...}],
      "post_tool_decisions": [{"tool": "getOrderStatus", "decision": "PASS", ...}],
      "llm_call": {"messages_count": 4, "tokens_in": 120, "tokens_out": 45, "duration_ms": 800},
      "firewall_decision": {"decision": "ALLOW", "risk_score": 0.05}
    }
  ],
  "final_response": "Your order ORD-123 has been shipped!",
  "total_duration_ms": 1250,
  "node_timings": {"input_node": 3.0, "intent_node": 1.0, "llm_call_node": 800.0},
  "counters": {"iterations": 1, "tool_calls": 1, "tool_calls_blocked": 0, "tokens_in": 120, "tokens_out": 45, "estimated_cost": 0.001},
  "limits_hit": null,
  "errors": []
}
```

### Test Coverage (31 tests)

- **Unit — TraceAccumulator:** lifecycle, intent, iterations, tool plan, pre-tool decisions,
  tool execution, post-tool decisions, LLM call, limits, node timing, finalize, to_dict
- **Integration — Node trace:** input_node starts trace, intent_node records, tool_executor records,
  pre_tool_gate records, post_tool_gate records, limit hit recorded, memory_node finalizes
- **Schema:** trace field on response, defaults to empty dict
- **End-to-end:** full trace lifecycle simulating complete agent flow

---

## Not Yet Implemented (Phase 2 & 3)

- DB persistence (`agent_traces` table)
- REST API endpoints (`GET /agent/traces`, `GET /agent/traces/{id}`)
- Langfuse integration
- Incident bundle export
- `?include_trace=true` query parameter (trace is always included for now)
