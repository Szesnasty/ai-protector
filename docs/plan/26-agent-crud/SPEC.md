# Step 26 — Agent CRUD API + DB Model

**Prereqs:** Steps 01–25 (MVP complete)
**Spec ref:** agents-v1.spec.md → Req 1
**Effort:** 1–2 days
**Output:** Agent registration API, DB model, risk classification

---

## Why first

Everything in the Agent Wizard depends on having an agent record in the database.
Tools, roles, config generation, validation, traces — all hang on `agent_id`.

---

## Sub-steps

### 26a — DB model + migration

| Item | Detail |
|------|--------|
| Table | `agents` |
| Columns | `id` (UUID), `name`, `description`, `team`, `framework` (enum: langgraph/raw_python/proxy_only), `environment` (enum: dev/staging/production), `is_public_facing` (bool), `has_tools` (bool), `has_write_actions` (bool), `touches_pii` (bool), `handles_secrets` (bool), `calls_external_apis` (bool), `risk_level` (enum: low/medium/high/critical, computed), `protection_level` (enum: proxy_only/agent_runtime/full), `policy_pack` (str, nullable), `rollout_mode` (enum: observe/warn/enforce, default observe), `status` (enum: draft/active/archived), `created_at`, `updated_at` |
| Migration | Alembic auto-generate |

**DoD:**
- [ ] SQLAlchemy model `Agent` with all columns above
- [ ] Alembic migration creates table
- [ ] Migration runs cleanly up and down
- [ ] Pydantic schemas: `AgentCreate`, `AgentUpdate`, `AgentResponse`

### 26b — Risk classification logic

Auto-compute `risk_level` from capabilities:

```
LOW:      !has_write_actions && !touches_pii && !handles_secrets && !is_public_facing
MEDIUM:   has_write_actions || (is_public_facing && has_tools)
HIGH:     (has_write_actions && is_public_facing) || touches_pii || handles_secrets
CRITICAL: has_write_actions && touches_pii && is_public_facing
```

Auto-recommend `protection_level`:

```
LOW    → proxy_only
MEDIUM → agent_runtime
HIGH   → full
CRITICAL → full
```

**DoD:**
- [ ] `compute_risk_level(agent)` function with deterministic rules above
- [ ] `recommend_protection_level(risk_level)` returns recommendation
- [ ] Risk is re-computed on every update (PATCH)
- [ ] Unit tests: all 4 risk levels covered with edge cases

### 26c — CRUD API endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents` | POST | Create agent, auto-compute risk |
| `/agents` | GET | List agents (paginated, filterable by status/risk/team) |
| `/agents/:id` | GET | Agent detail |
| `/agents/:id` | PATCH | Update agent, re-compute risk |
| `/agents/:id` | DELETE | Soft-delete (set status=archived) |

**DoD:**
- [ ] All 5 endpoints working
- [ ] POST returns computed `risk_level` + recommended `protection_level`
- [ ] GET list supports `?status=active&risk_level=high&team=platform`
- [ ] PATCH re-computes risk when capability fields change
- [ ] DELETE sets `status=archived`, doesn't hard-delete
- [ ] Validation: name required, min 2 chars
- [ ] Tests: CRUD cycle, risk computation, filtering, soft-delete

### 26d — Seed demo agent

Insert the existing Customer Support Copilot as a pre-configured reference agent.

**DoD:**
- [ ] Seed script creates "Customer Support Copilot" agent with status=active, is_reference=true
- [ ] Reference agent is non-deletable (API returns 403)
- [ ] Reference agent appears at top of agents list
