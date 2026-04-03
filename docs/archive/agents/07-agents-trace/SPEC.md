# 07 — Agent Trace (Evidence and Step-by-Step Debugging)

> **Priority:** 7
> **Depends on:** 01 (Pre-tool Gate), 03 (Post-tool Gate), 06 (Limits)
> **Used by:** 08 (Deterministic Test), 09 (Node Timings)
> **Sprint:** 3

---

## 1. Goal

Give developers and users "proof" of what happened: why the agent did something, what the model proposed, what the firewall blocked, and how decisions were made. Without trace:
- You cannot tune policies
- You cannot debug false positives/negatives
- You cannot answer "why was my request blocked?"
- You cannot reproduce issues
- You have no audit trail for compliance

---

## 2. Current State

Today in `agent-demo`:
- `tool_calls` list tracks tool invocations (name, args, result, allowed)
- `node_timings` dict tracks time per node
- `firewall_decision` captures the proxy's verdict
- `errors` list captures non-fatal errors

**What's missing:**
- No structured trace object per iteration
- No pre-tool gate / post-tool gate decisions recorded
- No model reasoning summary
- No trace persistence (in-memory only, lost after request)
- No export capability
- No Langfuse integration from agent side
- Tool results don't distinguish raw vs sanitized

---

## 3. Target Architecture

### 3.1. Trace Structure

Each agent request produces a **Trace** — a structured record of everything that happened:

```
Trace
├── trace_id: UUID
├── session_id: string
├── request_id: string
├── timestamp: ISO datetime
├── user_role: string
├── policy: string
├── model: string
├── user_message: string
├── intent: string (+ confidence)
│
├── iterations: [
│   ├── Iteration 1
│   │   ├── tool_plan: [{tool, args}]
│   │   ├── pre_tool_decisions: [{tool, decision, reason, checks}]
│   │   ├── tool_executions: [{tool, args, raw_result, duration_ms}]
│   │   ├── post_tool_decisions: [{tool, decision, pii_count, injection_score}]
│   │   ├── sanitized_results: [{tool, sanitized_result}]
│   │   ├── llm_call: {messages_count, tokens_in, tokens_out, duration_ms}
│   │   └── firewall_decision: {decision, risk_score, flags}
│   └── ...
│
├── final_response: string
├── total_duration_ms: int
├── node_timings: {node: ms}
├── counters: {iterations, tool_calls, tokens_in, tokens_out, estimated_cost}
├── limits_hit: string | null
└── errors: [string]
```

### 3.2. Trace Lifecycle

```
input_node → Start trace
     │
intent_node → Record intent
     │
policy_check → Record allowed_tools
     │
tool_router → Record tool_plan
     │
pre_tool_gate → Record gate decisions
     │
tool_executor → Record tool results + timing
     │
post_tool_gate → Record output scanning results
     │
llm_call → Record LLM call details + firewall decision
     │
response_node → Record final_response
     │
memory_node → Finalize trace, persist
```

---

## 4. How It Works

### 4.1. Trace Accumulator

A `TraceAccumulator` is added to `AgentState`:

```python
class TraceAccumulator:
    def start(self, session_id, request_id, user_role, policy, model, user_message): ...
    def record_intent(self, intent, confidence): ...
    def start_iteration(self): ...
    def record_tool_plan(self, plans): ...
    def record_pre_tool_decision(self, tool, decision, reason, checks): ...
    def record_tool_execution(self, tool, args, result, duration_ms): ...
    def record_post_tool_decision(self, tool, decision, scan_results): ...
    def record_llm_call(self, messages_count, tokens_in, tokens_out, duration_ms, firewall): ...
    def record_node_timing(self, node_name, duration_ms): ...
    def finalize(self, final_response, errors): ...
    def to_dict(self) -> dict: ...
    def to_json(self) -> str: ...
```

Every node calls the appropriate `record_*` method. The trace is built incrementally.

### 4.2. Persistence

After `memory_node` finalizes the trace:

1. **Database:** store in `agent_traces` table (or as JSONB in the requests table)
2. **Langfuse:** send as a trace with spans per node (optional, like the proxy does)
3. **Log:** emit structured log with trace summary (for log aggregation)

### 4.3. API

```
GET /agent/traces                     → List traces (paginated, filterable)
GET /agent/traces/{trace_id}          → Full trace detail
GET /agent/traces/{trace_id}/export   → Download as JSON (incident bundle)
```

Filters: `session_id`, `user_role`, `decision`, `date_from`, `date_to`, `has_blocks`

### 4.4. Incident Bundle Export

A trace can be exported as a self-contained JSON file for incident analysis:

```json
{
  "trace_id": "abc-123",
  "exported_at": "2026-03-05T10:30:00Z",
  "session_id": "sess-456",
  "user_message": "show me all user emails",
  "iterations": [...],
  "final_response": "I can't share other users' information.",
  "summary": {
    "blocks": 2,
    "redactions": 1,
    "total_duration_ms": 1250
  }
}
```

---

## 5. Data Structures

### 5.1. TraceIteration

```python
class TraceIteration(TypedDict):
    iteration: int
    tool_plan: list[dict]
    pre_tool_decisions: list[dict]
    tool_executions: list[dict]
    post_tool_decisions: list[dict]
    llm_call: dict | None
    firewall_decision: dict | None
```

### 5.2. AgentTrace

```python
class AgentTrace(TypedDict):
    trace_id: str
    session_id: str
    request_id: str
    timestamp: str
    user_role: str
    policy: str
    model: str
    user_message: str
    intent: str
    intent_confidence: float
    iterations: list[TraceIteration]
    final_response: str
    total_duration_ms: int
    node_timings: dict[str, float]
    counters: dict[str, int]
    limits_hit: str | None
    errors: list[str]
```

### 5.3. AgentState Addition

```python
class AgentState(TypedDict, total=False):
    # ... existing ...
    trace: dict  # NEW: serialized AgentTrace being built
```

---

## 6. Implementation Phases

Trace is scope-creep-prone. Split into phases to deliver value incrementally:

### Phase 1 — In-memory trace + API response (Sprint 3, ~2 days)

- [x] **6a.** Define `AgentTrace`, `TraceIteration` data structures
- [x] **6b.** Create `src/agent/trace/accumulator.py` with `TraceAccumulator` class
- [x] **6c.** Update `input_node` to start trace
- [x] **6d.** Update `intent_node` to record intent
- [x] **6e.** Update `tool_router_node` to record tool plan
- [x] **6f.** Update `pre_tool_gate` to record gate decisions (when implemented)
- [x] **6g.** Update `tool_executor_node` to record tool results + timing
- [x] **6h.** Update `post_tool_gate` to record scan results (when implemented)
- [x] **6i.** Update `llm_call_node` to record LLM call details
- [x] **6j.** Return trace in `/agent/chat` response body (opt-in via `?include_trace=true`)
- [x] **6k.** Write tests: trace is built correctly across full agent flow

**Deliverable:** every agent request produces a structured trace returned in the response.
No persistence yet — trace lives in memory for the duration of the request.

### Phase 2 — DB persistence + REST API (Sprint 4, ~3 days)

- [x] **6l.** Create `agent_traces` DB table (JSONB storage)
- [x] **6m.** Update `memory_node` to persist trace to DB
- [x] **6n.** Create API endpoints: `GET /agent/traces`, `GET /agent/traces/{trace_id}`
- [x] **6o.** Add filters: `session_id`, `user_role`, `decision`, `date_from`, `date_to`, `has_blocks`
- [x] **6p.** Write tests: trace persistence, filters, pagination

**Deliverable:** traces are persisted and queryable via API.

### Phase 3 — Langfuse integration + export (Sprint 4, ~1 day)

- [x] **6q.** Add Langfuse trace integration (spans per node, optional)
- [x] **6r.** Create `GET /agent/traces/{trace_id}/export` — JSON incident bundle
- [x] **6s.** Write tests: trace export produces valid JSON

**Deliverable:** traces visible in Langfuse; exportable as self-contained incident bundles.

---

## 7. Test Scenarios

| Scenario | Expected |
|----------|----------|
| Normal request (tool call → response) | Trace has 1 iteration with tool plan, execution, LLM call |
| Blocked tool call | Trace shows pre-tool gate `BLOCK` with reason |
| PII in tool output | Trace shows post-tool gate `REDACT` with pii_count > 0 |
| Multi-turn conversation | Each turn produces a separate trace, linked by session_id |
| Limit exceeded | Trace shows `limits_hit` field with limit type |
| Export trace as JSON | Valid JSON with all fields populated |

---

## 8. Definition of Done

### Phase 1 (MVP)
- [x] `TraceAccumulator` builds structured trace per request
- [x] Every node contributes to the trace
- [x] Pre-tool and post-tool gate decisions are recorded
- [x] Trace returned in API response
- [x] Node timings are recorded per node
- [x] Counters track iterations, tool calls, tokens, cost
- [x] Tests pass for full trace lifecycle

### Phase 2
- [x] Trace is persisted to DB (JSONB)
- [x] API endpoints work (list, detail) with filters
- [x] Tests pass for persistence and filters

### Phase 3
- [x] Langfuse integration sends spans per node
- [x] Trace export produces valid, self-contained JSON
- [x] Export endpoint works
