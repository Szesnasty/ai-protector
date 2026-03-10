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
