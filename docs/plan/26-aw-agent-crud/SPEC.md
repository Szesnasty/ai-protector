# Step 26 — Agent CRUD API + DB Model

**Prereqs:** Steps 01–25 (MVP complete)
**Spec ref:** agents-v1.spec.md → Req 1
**Effort:** 1–2 days
**Output:** Agent registration API, DB model, risk classification

**Module:** All wizard code lives in the self-contained `src/wizard/` package:

```
src/wizard/
    __init__.py              # Exports wizard_router + seed_wizard
    router.py                # Composite router mounting all sub-routers
    models.py                # Agent model + enums (this spec)
    schemas.py               # Pydantic schemas (this spec)
    seed.py                  # Reference agent seed (this spec)
    routers/agents.py        # Agent CRUD endpoints (this spec)
    services/risk.py         # Risk classification (this spec)
tests/wizard/
    test_agent_crud.py       # Tests for this spec
alembic/versions/
    *_aw_001_agents.py       # Migration (prefix aw_ for wizard)
```

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
- [x] SQLAlchemy model `Agent` with all columns above
- [x] Alembic migration creates table
- [x] Migration runs cleanly up and down
- [x] Pydantic schemas: `AgentCreate`, `AgentUpdate`, `AgentResponse`

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
- [x] `compute_risk_level(agent)` function with deterministic rules above
- [x] `recommend_protection_level(risk_level)` returns recommendation
- [x] Risk is re-computed on every update (PATCH)
- [x] Unit tests: all 4 risk levels covered with edge cases

### 26c — CRUD API endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents` | POST | Create agent, auto-compute risk |
| `/agents` | GET | List agents (paginated, filterable by status/risk/team) |
| `/agents/:id` | GET | Agent detail |
| `/agents/:id` | PATCH | Update agent, re-compute risk |
| `/agents/:id` | DELETE | Soft-delete (set status=archived) |

**DoD:**
- [x] All 5 endpoints working
- [x] POST returns computed `risk_level` + recommended `protection_level`
- [x] GET list supports `?status=active&risk_level=high&team=platform`
- [x] PATCH re-computes risk when capability fields change
- [x] DELETE sets `status=archived`, doesn't hard-delete
- [x] Validation: name required, min 2 chars
- [x] Tests: CRUD cycle, risk computation, filtering, soft-delete

### 26d — Seed demo agent

Insert the existing Customer Support Copilot as a pre-configured reference agent.

**DoD:**
- [x] Seed script creates "Customer Support Copilot" agent with status=active, is_reference=true
- [x] Reference agent is non-deletable (API returns 403)
- [x] Reference agent appears at top of agents list

---

## Test plan

Minimum **35 tests** across 4 sub-steps. All tests in `tests/wizard/test_agent_crud.py`.

### 26a tests — DB model (6 tests)

| # | Test | Assert |
|---|------|--------|
| 1 | `test_create_agent_model` | Agent row inserted, id is UUID, created_at auto-set |
| 2 | `test_agent_default_values` | status=draft, rollout_mode=observe, risk_level=null before compute |
| 3 | `test_agent_framework_enum` | Only langgraph/raw_python/proxy_only accepted |
| 4 | `test_agent_environment_enum` | Only dev/staging/production accepted |
| 5 | `test_migration_up_down` | Alembic upgrade → table exists, downgrade → table gone |
| 6 | `test_pydantic_schemas_validation` | AgentCreate rejects missing name, AgentUpdate allows partial |

### 26b tests — Risk classification (12 tests)

| # | Test | Assert |
|---|------|--------|
| 7 | `test_risk_low` | !write && !pii && !secrets && !public → LOW |
| 8 | `test_risk_medium_write` | write && !pii && !public → MEDIUM |
| 9 | `test_risk_medium_public_tools` | public && tools && !write → MEDIUM |
| 10 | `test_risk_high_write_public` | write && public → HIGH |
| 11 | `test_risk_high_pii` | pii=true (any combo) → HIGH |
| 12 | `test_risk_high_secrets` | secrets=true (any combo) → HIGH |
| 13 | `test_risk_critical` | write && pii && public → CRITICAL |
| 14 | `test_risk_all_false` | All capabilities false → LOW |
| 15 | `test_risk_all_true` | All capabilities true → CRITICAL |
| 16 | `test_protection_level_low` | risk LOW → proxy_only |
| 17 | `test_protection_level_medium` | risk MEDIUM → agent_runtime |
| 18 | `test_protection_level_high_critical` | risk HIGH/CRITICAL → full |

### 26c tests — CRUD API (13 tests)

| # | Test | Assert |
|---|------|--------|
| 19 | `test_post_creates_agent` | POST /agents → 201, body has id + computed risk |
| 20 | `test_post_missing_name` | POST /agents {} → 422 validation error |
| 21 | `test_post_name_too_short` | POST name="a" → 422 |
| 22 | `test_post_duplicate_name` | POST same name twice → 409 conflict |
| 23 | `test_get_list_empty` | GET /agents → 200, items=[] |
| 24 | `test_get_list_pagination` | Create 15 agents, GET ?page=2&per_page=10 → 5 items, total=15 |
| 25 | `test_get_list_filter_status` | GET ?status=active → only active agents |
| 26 | `test_get_list_filter_risk` | GET ?risk_level=high → only high-risk agents |
| 27 | `test_get_list_filter_team` | GET ?team=platform → only platform team agents |
| 28 | `test_get_detail` | GET /agents/:id → 200, full agent object |
| 29 | `test_get_detail_not_found` | GET /agents/nonexistent → 404 |
| 30 | `test_patch_updates_and_recomputes_risk` | PATCH touches_pii=true → risk re-computed to HIGH |
| 31 | `test_delete_soft_deletes` | DELETE → status=archived, still in DB, not in active list |

### 26d tests — Seed (4 tests)

| # | Test | Assert |
|---|------|--------|
| 32 | `test_seed_creates_reference_agent` | After seed, "Customer Support Copilot" exists |
| 33 | `test_reference_agent_non_deletable` | DELETE reference agent → 403 |
| 34 | `test_reference_agent_top_of_list` | GET /agents → reference agent first |
| 35 | `test_seed_idempotent` | Run seed twice → still 1 reference agent, no duplicates |
