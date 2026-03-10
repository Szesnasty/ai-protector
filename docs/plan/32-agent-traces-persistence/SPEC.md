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
