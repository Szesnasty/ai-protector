# Step 32 — Agent Traces & Incidents Persistence

**Prereqs:** Step 31 (Rollout Modes)
**Spec ref:** agents-v1.spec.md → Req 7
**Effort:** 2 days
**Output:** Per-agent traces stored in DB, queryable via API, incident grouping

---

## Why this step matters

Traces are what the user reads to decide:
- Is this config correct? (observe mode)
- Are there false positives to tune? (warn mode)
- Did we block a real attack? (enforce mode)

Without traces, the agent firewall is a black box.

**Distinction from existing proxy request log:**
The proxy already logs requests in `request_log`. Agent traces are different:
- Scoped to an **agent**, not to a proxy request
- Track **tool-level decisions** (pre-tool gate, post-tool gate)
- Include **rollout_mode** and **enforced** flags
- Support **incident grouping** (multiple related traces → one incident)

---

## Sub-steps

### 32a — Trace DB model

```python
class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id: Mapped[uuid.UUID]
    agent_id: Mapped[uuid.UUID]             # FK → agents
    session_id: Mapped[str]                 # groups traces in one conversation
    timestamp: Mapped[datetime]
    gate: Mapped[str]                       # "pre_tool" | "post_tool" | "pre_llm" | "post_llm"
    tool_name: Mapped[str | None]           # null for LLM gates
    role: Mapped[str | None]                # user role at request time
    decision: Mapped[str]                   # "ALLOW" | "DENY" | "REDACT" | "WARN"
    reason: Mapped[str]                     # human-readable reason
    category: Mapped[str]                   # "rbac" | "injection" | "pii" | "budget" | "policy"
    rollout_mode: Mapped[str]               # "observe" | "warn" | "enforce"
    enforced: Mapped[bool]                  # true only if mode=enforce
    latency_ms: Mapped[int]                 # gate evaluation time
    details: Mapped[dict]                   # JSONB — extra context (input snippet, matched pattern, etc.)
    incident_id: Mapped[uuid.UUID | None]   # FK → agent_incidents (null if no incident)
```

**DoD:**
- [ ] Alembic migration creates `agent_traces` table
- [ ] Model with all fields above
- [ ] Indexes: `agent_id + timestamp`, `agent_id + session_id`, `incident_id`
- [ ] Tests: create trace, read back, verify all fields

### 32b — Incident model

An incident = one or more traces that represent a security event worth attention.

```python
class AgentIncident(Base):
    __tablename__ = "agent_incidents"

    id: Mapped[uuid.UUID]
    agent_id: Mapped[uuid.UUID]
    severity: Mapped[str]                   # "low" | "medium" | "high" | "critical"
    category: Mapped[str]                   # "rbac_violation" | "injection_attempt" | "pii_leak" | "budget_exceeded"
    title: Mapped[str]                      # e.g. "RBAC violation: viewer role attempted admin tool"
    status: Mapped[str]                     # "open" | "acknowledged" | "resolved" | "false_positive"
    first_seen: Mapped[datetime]
    last_seen: Mapped[datetime]
    trace_count: Mapped[int]                # denormalized for list view
    details: Mapped[dict]                   # JSONB
```

Severity rules (deterministic, no LLM):
- RBAC violation in enforce: HIGH
- Injection detected: CRITICAL
- PII in output (unredacted): HIGH
- Budget exceeded: MEDIUM
- Any decision in observe/warn: LOW (informational)

**DoD:**
- [ ] Alembic migration creates `agent_incidents` table
- [ ] Model with all fields above
- [ ] FK from `agent_traces.incident_id` → `agent_incidents.id`
- [ ] Tests: create incident with traces, verify relationship

### 32c — Trace recording service

Service that gates call to record decisions:

```python
class TraceRecorder:
    async def record(self, agent_id, gate, tool_name, role,
                     decision, reason, category, rollout_mode,
                     enforced, latency_ms, details, session_id) -> AgentTrace:
        # 1. Insert trace
        # 2. If decision is DENY/REDACT/WARN:
        #    a. Find or create incident (same agent + category + 1h window)
        #    b. Link trace to incident
        #    c. Update incident.last_seen + trace_count
        # 3. Return trace
```

Incident grouping:
- Same agent + same category + within 1 hour → same incident
- Otherwise → new incident
- This groups things like "5 RBAC violations from same session"

**DoD:**
- [ ] `record()` creates trace + optional incident
- [ ] Incident deduplication by agent + category + time window
- [ ] Recorder is async with DB session management
- [ ] Tests: 3 same-category traces within 1h → 1 incident, 2 traces 2h apart → 2 incidents

### 32d — Traces API

```
GET /agents/:id/traces
  ?page=1&per_page=50
  &gate=pre_tool
  &decision=DENY
  &category=rbac
  &rollout_mode=observe
  &session_id=abc
  &from=2026-03-01T00:00:00Z
  &to=2026-03-10T00:00:00Z

→ { items: [...], total: 150, page: 1, per_page: 50 }
```

```
GET /agents/:id/incidents
  ?status=open
  &severity=high
  &category=injection_attempt

→ { items: [...], total: 3 }
```

```
PATCH /agents/:id/incidents/:incident_id
Body: { "status": "resolved" }
```

**DoD:**
- [ ] Traces list with filtering + pagination
- [ ] Incidents list with filtering
- [ ] Incident status update (acknowledge, resolve, mark false positive)
- [ ] Tests: create traces via recorder, query back via API with filters

### 32e — Trace statistics endpoint

```
GET /agents/:id/traces/stats
  ?from=2026-03-01T00:00:00Z
  &to=2026-03-10T00:00:00Z

→ {
    total_evaluations: 1500,
    by_decision: { ALLOW: 1450, DENY: 30, REDACT: 15, WARN: 5 },
    by_category: { rbac: 20, injection: 10, pii: 15, budget: 5 },
    by_gate: { pre_tool: 900, post_tool: 600 },
    avg_latency_ms: 3,
    incidents: { open: 2, acknowledged: 1, resolved: 5 }
  }
```

**DoD:**
- [ ] Stats endpoint with aggregated data
- [ ] Time range filtering
- [ ] Breakdown by decision, category, gate
- [ ] Tests: create known traces, verify stats match

---

## Test plan

Minimum **50 tests** across 5 sub-steps. Tests in `tests/agents/test_traces.py`
and `tests/agents/test_incidents.py`.

### 32a tests — Trace DB model (10 tests)

| # | Test | Assert |
|---|------|--------|
| 1 | `test_create_trace` | Insert trace, all fields persisted |
| 2 | `test_trace_uuid_auto_generated` | id is UUID, auto-set |
| 3 | `test_trace_timestamp_auto_set` | timestamp defaults to now |
| 4 | `test_trace_fk_agent` | agent_id must reference existing agent (FK constraint) |
| 5 | `test_trace_gate_values` | Only pre_tool/post_tool/pre_llm/post_llm accepted |
| 6 | `test_trace_decision_values` | Only ALLOW/DENY/REDACT/WARN accepted |
| 7 | `test_trace_details_jsonb` | details field stores and retrieves complex JSON |
| 8 | `test_trace_index_agent_timestamp` | Query by agent_id + timestamp range is fast (index used) |
| 9 | `test_trace_index_agent_session` | Query by agent_id + session_id uses index |
| 10 | `test_migration_up_down` | Upgrade creates table, downgrade drops it |

### 32b tests — Incident model (10 tests)

| # | Test | Assert |
|---|------|--------|
| 11 | `test_create_incident` | Insert incident, all fields persisted |
| 12 | `test_incident_severity_values` | Only low/medium/high/critical accepted |
| 13 | `test_incident_status_values` | Only open/acknowledged/resolved/false_positive accepted |
| 14 | `test_incident_default_status` | New incident → status=open |
| 15 | `test_incident_trace_count` | trace_count matches linked traces |
| 16 | `test_incident_fk_agent` | agent_id must reference existing agent |
| 17 | `test_trace_incident_fk` | trace.incident_id references incident |
| 18 | `test_severity_rbac_enforce` | RBAC violation in enforce → severity=HIGH |
| 19 | `test_severity_injection` | Injection detected → severity=CRITICAL |
| 20 | `test_severity_observe_mode` | Any decision in observe → severity=LOW |

### 32c tests — Trace recording service (12 tests)

| # | Test | Assert |
|---|------|--------|
| 21 | `test_record_allow_no_incident` | ALLOW decision → trace created, no incident |
| 22 | `test_record_deny_creates_incident` | DENY decision → trace + incident created |
| 23 | `test_record_redact_creates_incident` | REDACT decision → trace + incident created |
| 24 | `test_record_warn_creates_incident` | WARN decision → trace + incident (low severity) |
| 25 | `test_incident_dedup_same_category_1h` | 3 DENY+rbac within 1h → 1 incident, 3 traces linked |
| 26 | `test_incident_dedup_different_category` | DENY+rbac + DENY+injection within 1h → 2 incidents |
| 27 | `test_incident_dedup_same_category_2h` | 2 DENY+rbac 2h apart → 2 separate incidents |
| 28 | `test_incident_last_seen_updated` | Second trace in incident → last_seen updated |
| 29 | `test_incident_trace_count_incremented` | 3 traces → incident.trace_count=3 |
| 30 | `test_recorder_async` | record() is async, works with async DB session |
| 31 | `test_recorder_concurrent_safety` | 10 concurrent record() calls → no race conditions |
| 32 | `test_recorder_incident_title_generated` | Title includes category + context (e.g., role + tool) |

### 32d tests — Traces API (12 tests)

| # | Test | Assert |
|---|------|--------|
| 33 | `test_get_traces_list` | GET /agents/:id/traces → paginated list |
| 34 | `test_get_traces_filter_gate` | ?gate=pre_tool → only pre_tool traces |
| 35 | `test_get_traces_filter_decision` | ?decision=DENY → only DENY traces |
| 36 | `test_get_traces_filter_category` | ?category=rbac → only rbac traces |
| 37 | `test_get_traces_filter_rollout_mode` | ?rollout_mode=observe → only observe traces |
| 38 | `test_get_traces_filter_session` | ?session_id=abc → only that session |
| 39 | `test_get_traces_filter_time_range` | ?from=...&to=... → only traces in range |
| 40 | `test_get_traces_pagination` | Create 60 traces, page=2&per_page=50 → 10 items, total=60 |
| 41 | `test_get_incidents_list` | GET /agents/:id/incidents → list |
| 42 | `test_get_incidents_filter_status` | ?status=open → only open incidents |
| 43 | `test_get_incidents_filter_severity` | ?severity=critical → only critical |
| 44 | `test_patch_incident_status` | PATCH status=resolved → 200, status updated |

### 32e tests — Trace statistics (6 tests)

| # | Test | Assert |
|---|------|--------|
| 45 | `test_stats_total_evaluations` | stats.total_evaluations matches trace count |
| 46 | `test_stats_by_decision` | by_decision breakdown matches actual |
| 47 | `test_stats_by_category` | by_category breakdown matches actual |
| 48 | `test_stats_by_gate` | by_gate breakdown matches actual |
| 49 | `test_stats_time_range_filter` | Stats with date range → only counts traces in range |
| 50 | `test_stats_incidents_count` | incidents.open/acknowledged/resolved match actual |
