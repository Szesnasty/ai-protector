# Step 01 — Fix Missing Alembic Migrations

> **Effort:** 1 hour
> **Depends on:** nothing
> **Blocks:** steps 03, 04 (agents need traces/incidents tables in production)

---

## Context

The wizard has 14 ORM models in `src/wizard/models.py`, but only 5 Alembic migrations
(`aw_001`–`aw_005`). The remaining models work in dev because `Base.metadata.create_all`
runs on startup, but they won't exist in a production-like DB without migrations.

### What's covered (existing migrations)

| Migration | Tables |
|-----------|--------|
| `aw_001` | `agents` |
| `aw_002` | `agent_tools`, `agent_roles`, `role_tool_permissions` |
| `aw_003` | `agents.generated_config` (JSONB column) |
| `aw_004` | `agents.generated_kit` (JSONB column) |
| `aw_005` | `validation_runs` |

### What's missing

| Model | Table | Used by |
|-------|-------|---------|
| `AgentTrace` | `agent_traces` | Trace recording (spec 32) |
| `AgentIncident` | `agent_incidents` | Incident auto-grouping |
| `GateDecision` | `gate_decisions` | Per-request gate results |
| `PromotionEvent` | `promotion_events` | Rollout mode change history |

---

## Implementation Plan

### Step 1: Generate migration `aw_006_traces_incidents`

```bash
cd apps/proxy-service
.venv/bin/alembic revision -m "aw_006_traces_incidents_gates_promotions" \
  --rev-id aw006traces
```

### Step 2: Write the migration

The migration should create 4 tables matching the ORM models in `src/wizard/models.py`:

**`agent_traces`:**
- `id` UUID PK
- `agent_id` UUID FK → agents.id
- `session_id` VARCHAR(100)
- `request_id` VARCHAR(100)
- `role` VARCHAR(100)
- `tool` VARCHAR(200) nullable
- `gate` VARCHAR(50) — enum: pre_tool, post_tool, rollout
- `decision` VARCHAR(50) — enum: allow, block, redact, confirm, log
- `reason` TEXT nullable
- `category` VARCHAR(100) nullable
- `details` JSONB nullable
- `latency_ms` FLOAT nullable
- `created_at` TIMESTAMP with TZ, default now

**`agent_incidents`:**
- `id` UUID PK
- `agent_id` UUID FK → agents.id
- `type` VARCHAR(100) — e.g. brute_force, privilege_probe, injection_spike
- `severity` VARCHAR(20) — low, medium, high, critical
- `status` VARCHAR(20) — open, acknowledged, resolved, false_positive
- `trace_ids` JSONB (list of trace UUIDs)
- `description` TEXT
- `created_at` TIMESTAMP with TZ
- `updated_at` TIMESTAMP with TZ

**`gate_decisions`:**
- `id` UUID PK
- `agent_id` UUID FK → agents.id
- `trace_id` UUID FK → agent_traces.id, nullable
- `gate` VARCHAR(50)
- `decision` VARCHAR(50)
- `role` VARCHAR(100)
- `tool` VARCHAR(200) nullable
- `reason` TEXT nullable
- `details` JSONB nullable
- `mode` VARCHAR(20) — observe, warn, enforce
- `created_at` TIMESTAMP with TZ

**`promotion_events`:**
- `id` UUID PK
- `agent_id` UUID FK → agents.id
- `from_mode` VARCHAR(20)
- `to_mode` VARCHAR(20)
- `reason` TEXT nullable
- `promoted_by` VARCHAR(200) nullable
- `created_at` TIMESTAMP with TZ

### Step 3: Add indexes

```python
# On agent_traces:
op.create_index("ix_agent_traces_agent_id", "agent_traces", ["agent_id"])
op.create_index("ix_agent_traces_created_at", "agent_traces", ["created_at"])

# On agent_incidents:
op.create_index("ix_agent_incidents_agent_id", "agent_incidents", ["agent_id"])

# On gate_decisions:
op.create_index("ix_gate_decisions_agent_id", "gate_decisions", ["agent_id"])

# On promotion_events:
op.create_index("ix_promotion_events_agent_id", "promotion_events", ["agent_id"])
```

### Step 4: Run and verify

```bash
# Apply migration
.venv/bin/alembic upgrade head

# Verify tables exist
.venv/bin/python -c "
from sqlalchemy import inspect, create_engine
engine = create_engine('postgresql://postgres:postgres@localhost:5432/ai_protector')
inspector = inspect(engine)
tables = inspector.get_table_names()
for t in ['agent_traces', 'agent_incidents', 'gate_decisions', 'promotion_events']:
    print(f'{t}: {\"✅\" if t in tables else \"❌\"}')"
```

### Step 5: Verify existing tests still pass

```bash
.venv/bin/python -m pytest tests/wizard/ -x -q
```

---

## Definition of Done

- [x] Migration file `aw_006_*` exists in `alembic/versions/`
- [x] `alembic upgrade head` succeeds without errors
- [x] All 4 tables exist in PostgreSQL with correct columns
- [x] Indexes created on `agent_id` and `created_at` columns
- [x] `alembic downgrade -1` cleanly drops the 4 tables
- [x] Existing wizard tests still pass (no regressions)
