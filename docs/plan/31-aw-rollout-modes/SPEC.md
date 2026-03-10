# Step 31 — Rollout Modes

**Prereqs:** Step 30 (Validation Runner)
**Spec ref:** agents-v1.spec.md → Req 6
**Effort:** 2 days
**Output:** observe / warn / enforce mode on agent gates with promotion flow

---

## Why this step matters

New config should NEVER go straight to production blocking mode.
Rollout modes give the user a safety ramp:

1. **Observe** — gates evaluate but NEVER block. Traces record what *would*
   have happened. User reads traces, tunes config.
2. **Warn** — gates evaluate and LOG warnings to user/agent but still ALLOW
   the action. Agent can surface warnings to end-user.
3. **Enforce** — gates evaluate and BLOCK/REDACT as configured.
   Production mode.

Transition: observe → warn → enforce is manual (user clicks "promote").
Cannot promote if validation score < 100% (all basic tests pass).

---

## Sub-steps

### 31a — DB model + enum

```python
class RolloutMode(str, Enum):
    OBSERVE = "observe"
    WARN = "warn"
    ENFORCE = "enforce"
```

Add `rollout_mode` column to `agents` table:
- Default: `OBSERVE`
- Not nullable

**DoD:**
- [ ] Alembic migration adds `rollout_mode` column (default OBSERVE)
- [ ] `AgentModel.rollout_mode` field
- [ ] `AgentRead` schema includes `rollout_mode`
- [ ] Tests: new agent gets OBSERVE, existing agents migrated to OBSERVE

### 31b — Gate behavior changes

Pre-tool gate + post-tool gate must respect rollout_mode:

| Mode | RBAC deny | Injection detected | PII in output | Over limit |
|---------|-----------|-------------------|---------------|------------|
| OBSERVE | ALLOW + trace(decision=DENY, enforced=false) | ALLOW + trace | PASS-THROUGH + trace | ALLOW + trace |
| WARN | ALLOW + trace + warning header | ALLOW + trace + warning | PASS-THROUGH + trace + warning | ALLOW + trace + warning |
| ENFORCE | DENY | BLOCK | REDACT | DENY |

Implementation approach:
- Gates already return decisions
- Add `enforced: bool` to decision result
- When mode ≠ ENFORCE: override action to ALLOW but keep original decision in trace
- When mode = WARN: add `X-AI-Protector-Warning` header or warning field in response

**DoD:**
- [ ] Gates accept `rollout_mode` parameter
- [ ] OBSERVE mode: all actions allowed, decisions traced with `enforced=false`
- [ ] WARN mode: all actions allowed, decisions traced, warning included in response
- [ ] ENFORCE mode: actions blocked/redacted as configured
- [ ] Traces include `rollout_mode` and `enforced` fields
- [ ] Tests: same request in 3 modes → different enforcement, same decision

### 31c — Promotion API

```
PATCH /agents/:id/rollout
Body: { "mode": "warn" }   # or "enforce"
```

Promotion rules:
- observe → warn: allowed if validation score exists (any score)
- warn → enforce: allowed if latest validation score = 100%
- enforce → warn: always allowed (downgrade)
- warn → observe: always allowed (downgrade)
- observe → enforce: NOT allowed (must go through warn)

```json
// Error response when trying to skip warn
{
  "error": "promotion_blocked",
  "reason": "Cannot promote directly from observe to enforce. Promote to warn first.",
  "current_mode": "observe",
  "requested_mode": "enforce"
}

// Error response when validation fails
{
  "error": "promotion_blocked",
  "reason": "Latest validation score is 10/12. All tests must pass to promote to enforce.",
  "current_mode": "warn",
  "requested_mode": "enforce",
  "latest_score": { "passed": 10, "total": 12 }
}
```

**DoD:**
- [ ] PATCH endpoint with mode validation
- [ ] Promotion rules enforced (no skip, no enforce without 100%)
- [ ] Returns updated agent with new rollout_mode
- [ ] Promotion event stored (agent_id, from_mode, to_mode, timestamp, user)
- [ ] Tests: all valid transitions succeed, all invalid transitions return 422

### 31d — Rollout mode in traces

Every trace/decision must include:
- `rollout_mode`: current mode at time of evaluation
- `enforced`: whether the decision was actually enforced (true only in ENFORCE)

This enables:
- "What would have been blocked?" queries in OBSERVE mode
- FP rate analysis before promoting to ENFORCE
- Audit trail of when modes changed

**DoD:**
- [ ] Trace schema includes `rollout_mode` and `enforced` fields
- [ ] `GET /agents/:id/traces?rollout_mode=observe` filter works
- [ ] FP count available: `GET /agents/:id/traces?enforced=false&decision=DENY`
- [ ] Tests: traces in each mode have correct rollout_mode + enforced values

### 31e — Promotion readiness check

```
GET /agents/:id/rollout/readiness
→ {
    current_mode: "observe",
    can_promote_to: ["warn"],
    blockers: [],
    stats: {
      traces_in_current_mode: 47,
      would_have_blocked: 3,
      false_positive_rate: null,   // needs manual review
      latest_validation: { passed: 12, total: 12, run_at: "..." }
    }
  }
```

**DoD:**
- [ ] Endpoint returns promotion options + blockers
- [ ] Stats computed from traces in current mode
- [ ] `would_have_blocked` = count of traces where decision=DENY and enforced=false
- [ ] Tests: readiness endpoint returns correct data for each mode

---

## Test plan

Minimum **48 tests** across 5 sub-steps. Tests in `tests/agents/test_rollout_modes.py`.

### 31a tests — DB model + enum (6 tests)

| # | Test | Assert |
|---|------|--------|
| 1 | `test_rollout_enum_values` | RolloutMode has observe, warn, enforce |
| 2 | `test_new_agent_default_observe` | New agent → rollout_mode=OBSERVE |
| 3 | `test_migration_existing_agents` | Pre-existing agents get OBSERVE after migration |
| 4 | `test_agent_read_includes_rollout` | AgentRead schema has rollout_mode field |
| 5 | `test_invalid_enum_value` | Setting rollout_mode="xxx" → error |
| 6 | `test_migration_up_down` | Upgrade adds column, downgrade removes it |

### 31b tests — Gate behavior changes (18 tests)

| # | Test | Assert |
|---|------|--------|
| 7 | `test_observe_rbac_deny_allows` | OBSERVE + RBAC deny → action ALLOWED |
| 8 | `test_observe_rbac_deny_traces` | OBSERVE + RBAC deny → trace with decision=DENY, enforced=false |
| 9 | `test_observe_injection_allows` | OBSERVE + injection detected → action ALLOWED |
| 10 | `test_observe_injection_traces` | OBSERVE + injection → trace with decision=BLOCKED, enforced=false |
| 11 | `test_observe_pii_passes_through` | OBSERVE + PII in output → not redacted, pass-through |
| 12 | `test_observe_budget_allows` | OBSERVE + over limit → action ALLOWED |
| 13 | `test_warn_rbac_deny_allows` | WARN + RBAC deny → action ALLOWED + warning |
| 14 | `test_warn_rbac_deny_has_warning` | WARN + RBAC deny → X-AI-Protector-Warning header or warning field |
| 15 | `test_warn_injection_allows_with_warning` | WARN + injection → ALLOWED + warning |
| 16 | `test_warn_pii_passes_with_warning` | WARN + PII → not redacted + warning |
| 17 | `test_warn_budget_allows_with_warning` | WARN + over limit → ALLOWED + warning |
| 18 | `test_enforce_rbac_denies` | ENFORCE + RBAC deny → DENIED |
| 19 | `test_enforce_injection_blocks` | ENFORCE + injection → BLOCKED |
| 20 | `test_enforce_pii_redacts` | ENFORCE + PII → REDACTED |
| 21 | `test_enforce_budget_denies` | ENFORCE + over limit → DENIED |
| 22 | `test_enforce_traces_enforced_true` | ENFORCE traces have enforced=true |
| 23 | `test_same_request_3_modes` | Identical input in 3 modes → same decision, different enforcement |
| 24 | `test_trace_has_rollout_mode` | Every trace includes rollout_mode field |

### 31c tests — Promotion API (14 tests)

| # | Test | Assert |
|---|------|--------|
| 25 | `test_promote_observe_to_warn` | PATCH mode=warn → 200 (with validation score present) |
| 26 | `test_promote_warn_to_enforce` | PATCH mode=enforce → 200 (validation 100%) |
| 27 | `test_promote_observe_to_enforce_blocked` | PATCH mode=enforce from observe → 422, skip not allowed |
| 28 | `test_promote_warn_to_enforce_low_score` | validation 10/12 → 422 with score details |
| 29 | `test_promote_warn_to_enforce_no_validation` | No validation run → 422 |
| 30 | `test_demote_enforce_to_warn` | PATCH mode=warn from enforce → 200 |
| 31 | `test_demote_warn_to_observe` | PATCH mode=observe from warn → 200 |
| 32 | `test_demote_enforce_to_observe` | PATCH mode=observe from enforce → 200 (or 422 if must go through warn) |
| 33 | `test_promote_same_mode` | PATCH current mode → 200 (no-op) |
| 34 | `test_promote_invalid_mode` | PATCH mode="xxx" → 422 |
| 35 | `test_promote_nonexistent_agent` | PATCH bad ID → 404 |
| 36 | `test_promotion_event_stored` | After promote, event in DB with from/to/timestamp |
| 37 | `test_promotion_events_history` | GET promotion events → ordered list |
| 38 | `test_returns_updated_agent` | PATCH response includes full agent with new rollout_mode |

### 31d tests — Rollout mode in traces (6 tests)

| # | Test | Assert |
|---|------|--------|
| 39 | `test_trace_observe_mode_field` | Trace in observe → rollout_mode="observe" |
| 40 | `test_trace_warn_mode_field` | Trace in warn → rollout_mode="warn" |
| 41 | `test_trace_enforce_mode_field` | Trace in enforce → rollout_mode="enforce" |
| 42 | `test_filter_traces_by_mode` | GET ?rollout_mode=observe → only observe traces |
| 43 | `test_filter_enforced_false_deny` | GET ?enforced=false&decision=DENY → FP candidates |
| 44 | `test_trace_mode_at_evaluation_time` | Promote mid-session → old traces keep old mode |

### 31e tests — Promotion readiness (4 tests)

| # | Test | Assert |
|---|------|--------|
| 45 | `test_readiness_observe_mode` | can_promote_to=["warn"], blockers=[] or ["no validation"] |
| 46 | `test_readiness_warn_mode_100pc` | can_promote_to=["enforce"], blockers=[] |
| 47 | `test_readiness_warn_mode_low_score` | can_promote_to=[], blockers=["validation score 10/12"] |
| 48 | `test_readiness_stats_computed` | traces_in_current_mode + would_have_blocked correct |
