# Agent Tracing — Centralized via Proxy-Service

> **Branch:** `feat/agent-wizard-tracing`
> **Depends on:** agent-demo tracing (spec 07), wizard traces (spec 32d)
> **Goal:** test-agents (pure-python, langgraph) send structured traces to
> proxy-service DB; frontend Agent Traces page reads from proxy-service.

---

## Status Quo

| Component | Current state |
|-----------|--------------|
| **agent-demo** | Full tracing: `TraceAccumulator` → `TraceStore` (in-memory) → `/agent/traces` API |
| **pure-python agent** | `gate_log` in `/chat` response only — no persistence, no `/traces` API |
| **langgraph agent** | Same — `gate_log` only, no trace collection |
| **proxy-service** | `POST /agents/{id}/traces/record` exists but stores **flat per-gate rows** (one row = one gate decision). No rich structured trace support |
| **frontend** | `agent-traces.vue` reads from agent-demo (`localhost:8002`). Agent detail Traces tab reads flat wizard traces from proxy-service |

**Problem:** Two incompatible trace formats — rich (agent-demo) vs flat (wizard).
Test agents produce neither. Frontend is hardcoded to agent-demo port.

---

## Target Architecture

```
┌─────────────┐   ┌─────────────────┐
│ pure-python  │   │ langgraph agent │
│   agent      │   │                 │
└──────┬───────┘   └────────┬────────┘
       │  POST /v1/agents/{id}/traces/ingest
       └──────────┬─────────┘
                  ▼
         ┌────────────────┐
         │  proxy-service  │  agent_trace_runs table (JSONB)
         │  /v1/agents/    │  + existing agent_traces (flat)
         │  {id}/traces/*  │
         └───────┬─────────┘
                 │  GET /v1/agents/{id}/traces/runs
                 ▼
         ┌────────────────┐
         │   frontend      │  Agent Traces page
         │   agent-traces  │  (reads from proxy-service)
         └────────────────┘
```

Key decisions:
- **New table** `agent_trace_runs` — stores full structured trace (JSONB), one row per agent request
- **Existing** `agent_traces` stays (flat per-gate records for wizard incident pipeline)
- **Ingest endpoint** accepts the same shape as agent-demo's `TraceAccumulator.to_dict()`
- **Shared library** `test-agents/shared/tracing.py` — lightweight `TraceCollector` that POSTs to proxy
- **Frontend** switches data source from agent-demo to proxy-service

---

## Steps

### Step 1 — DB model `AgentTraceRun` + migration

Add `agent_trace_runs` table:

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| agent_id | UUID FK → agents | indexed |
| trace_id | VARCHAR(64) | unique, from TraceAccumulator |
| session_id | VARCHAR(128) | indexed |
| timestamp | TIMESTAMPTZ | server_default=now() |
| user_role | VARCHAR(128) | |
| model | VARCHAR(128) | |
| intent | VARCHAR(128) | nullable |
| total_duration_ms | INT | |
| counters | JSONB | {iterations, tool_calls, tool_calls_blocked, tokens_in, tokens_out} |
| iterations | JSONB | full iterations array |
| errors | JSONB | [] |
| limits_hit | VARCHAR(64) | nullable |
| details | JSONB | overflow: node_timings, policy, user_message, final_response |

**DoD:**
- [ ] Model in `src/wizard/models.py`
- [ ] Alembic migration passes up + down
- [ ] `pytest` model instantiation test

### Step 2 — Schemas + ingest endpoint

`POST /v1/agents/{agent_id}/traces/ingest` — accepts full trace dict.
`GET /v1/agents/{agent_id}/traces/runs` — paginated list with filters.
`GET /v1/agents/{agent_id}/traces/runs/{trace_id}` — full detail.

Schemas: `TraceRunCreate`, `TraceRunSummary`, `TraceRunDetail`, `TraceRunListResponse`.

**DoD:**
- [ ] Pydantic schemas in `src/wizard/schemas.py`
- [ ] Router in `src/wizard/routers/trace_runs.py`
- [ ] Ingest validates `agent_id` exists, stores row, returns 201
- [ ] List returns summaries (no iterations blob), supports: `session_id`, `user_role`, `has_blocks`, `date_from`, `date_to`
- [ ] Detail returns full trace with iterations
- [ ] Tests: ingest → list → detail round-trip

### Step 3 — Shared TraceCollector for test agents

`test-agents/shared/tracing.py`:

```python
class TraceCollector:
    """Lightweight trace builder + HTTP sender."""
    def __init__(self, proxy_url: str, agent_id: str): ...
    def start(self, *, session_id, user_role, model=""): ...
    def start_iteration(self): ...
    def record_pre_tool(self, tool, decision, reason, checks): ...
    def record_tool_exec(self, tool, args, result, duration_ms): ...
    def record_post_tool(self, tool, decision, findings): ...
    def record_firewall(self, decision, intent, risk_score, reason): ...
    def finalize(self, final_response, errors=None): ...
    async def flush(self) -> bool:  # POST to proxy-service
```

Re-uses logic from agent-demo's `TraceAccumulator` but adds `flush()` HTTP call.

**DoD:**
- [ ] `shared/tracing.py` with `TraceCollector` class
- [ ] `flush()` POSTs to `/v1/agents/{agent_id}/traces/ingest`
- [ ] Unit test: build trace → `to_dict()` matches expected shape
- [ ] Integration test: `flush()` → verify row in DB (with test fixtures)

### Step 4 — Instrument pure-python agent

Wire `TraceCollector` into `main.py`:
- `_chat_mock()`: start → pre_tool → tool_exec → post_tool → finalize → flush
- `_chat_llm()`: start → firewall scan → LLM call → pre_tool → tool_exec → post_tool → finalize → flush
- Add `AGENT_ID` env var (set by docker-compose / load-config)
- Return `trace_id` in `/chat` response

**DoD:**
- [ ] Every `/chat` call produces a trace flushed to proxy-service
- [ ] `gate_log` still present in response (backward compat)
- [ ] `trace_id` returned in response body
- [ ] Mock mode test: trace arrives in DB with correct pre/post decisions
- [ ] LLM mode test: trace includes firewall_decision

### Step 4b — Migrate agent-demo to centralized tracing

Replace in-memory `TraceStore.save()` with HTTP flush to proxy-service:
- After `trace.finalize()` in `memory_node`, POST to `/v1/agents/{id}/traces/ingest`
- Remove `TraceStore` singleton + `/agent/traces` local endpoints
- agent-demo gets `AGENT_ID` env var (same as test agents)
- Keep `TraceAccumulator` — it builds the dict, only persistence changes

**DoD:**
- [ ] `memory_node` flushes trace to proxy-service via `httpx.AsyncClient`
- [ ] Local `/agent/traces`, `/agent/traces/{id}`, `/agent/traces/{id}/export` removed
- [ ] `TraceStore` + `store.py` removed (no more in-memory persistence)
- [ ] Existing tests updated to assert trace lands in proxy-service DB
- [ ] agent-demo traces visible in same frontend Agent Traces page as test agents

### Step 5 — Instrument langgraph agent

Wire `TraceCollector` into graph nodes + `main.py`:
- Add `trace: dict` to `AgentState`
- `route_tool_node`: start trace
- `pre_tool_gate_node`: `record_pre_tool()`
- `tool_executor_node`: `record_tool_exec()`
- `post_tool_gate_node`: `record_post_tool()`
- `response_node`: finalize
- `_chat_mock()` / `_chat_llm()`: after `graph.invoke()`, flush trace
- Same `AGENT_ID` env var

**DoD:**
- [ ] Every `/chat` call produces a trace flushed to proxy-service
- [ ] `gate_log` still present (backward compat)
- [ ] `trace_id` returned in response body
- [ ] Graph state carries trace through all nodes
- [ ] Test: full graph run → trace with iterations in DB

### Step 6 — Frontend: switch data source to proxy-service

Update `useAgentTraces.ts`:
- Change `baseURL` from agent-demo (`8002`) to proxy-service (`8000`)
- Update API paths: `/v1/agents/{agentId}/traces/runs`
- Add agent selector (dropdown or from route param)
- Type mappings: `TraceRunSummary` → existing `AgentTraceSummary` (shapes match by design)

**DoD:**
- [ ] Agent Traces page loads data from proxy-service
- [ ] Agent selector lets user pick which agent's traces to view
- [ ] Expand row shows full iteration detail (pre/post/tool_exec)
- [ ] Filters work (session, role, date range, has_blocks)
- [ ] Export still works (returns full trace JSON)

### Step 7 — Docker-compose + env wiring

- Add `AGENT_ID` and `PROXY_URL` to test-agent services in `docker-compose.yml`
- Agents auto-register on startup or receive ID via `/load-config`
- Verify full flow: start stack → load config → chat → trace visible in UI

**DoD:**
- [ ] `docker compose up` — both agents send traces after `/load-config`
- [ ] Agent Traces page shows traces from both agents
- [ ] No manual env setup required beyond `docker compose up`

---

## Out of Scope

- Langfuse integration (future — separate spec)
- Real-time WebSocket trace streaming
- Trace retention / archival policies

## Risk

| Risk | Mitigation |
|------|-----------|
| JSONB query perf at scale | Add GIN index on `counters`, partition by month later |
| Trace payload too large | Cap `iterations` JSONB at 512 KB in ingest endpoint |
| Agent can't reach proxy | `flush()` is fire-and-forget with warning log; agent still works |
