# Step 7 — Deploy with Rollout Modes

**Time: 5 minutes**
**Input: passing attack validation**
**Output: production-safe deployment with gradual enforcement**

---

## Why this step matters

You don't flip security on overnight. AI Protector uses **rollout
modes** to let you deploy safely:

1. **Observe** — log everything, block nothing
2. **Warn** — log + alert, but allow through
3. **Enforce** — block violations, redact PII

> **Strict mode (v2):** A fourth mode (fail-closed on errors, block uncertain) is planned for v2 for high-risk agents (finance, healthcare). Not in v1 scope.

This is the same pattern used by WAFs, CSPs, and feature flags.
You start in observe, watch for false positives, then promote.

---

## Rollout mode comparison

| Mode | Blocks | Redacts | Alerts | Logs | False positive risk |
|------|--------|---------|--------|------|---------------------|
| `observe` | No | No | No | Yes | None (read-only) |
| `warn` | No | No | Yes | Yes | Low (alerts only) |
| `enforce` | Yes | Yes | Yes | Yes | Medium (blocks bad) |

---

## Configuration

### Single environment

```yaml
# .env.protector
AI_PROTECTOR_MODE=observe
```

### Per-environment

```yaml
# config/rollout.yaml

environments:
  development:
    mode: enforce
    fail_open: true           # if gate errors, allow through
    log_level: debug

  staging:
    mode: enforce
    fail_open: false
    log_level: info

  production:
    mode: observe             # start here
    fail_open: true
    log_level: warn
    promotion:
      auto: false             # manual promotion only
      require_validation: true
```

### Per-policy overrides

Different policies can have different rollout modes:

```yaml
# config/rollout.yaml

policy_overrides:
  # RBAC is well-tested, enforce immediately
  rbac:
    mode: enforce

  # PII redaction needs calibration
  pii_redaction:
    mode: warn
    false_positive_threshold: 5%  # auto-demote if >5%

  # New injection patterns still tuning
  injection_detection:
    mode: observe

  # Budget limits are deterministic, safe to enforce
  rate_limits:
    mode: enforce

  budget:
    mode: enforce
```

---

## Recommended rollout timeline

### Week 1: Observe

```
Mode: observe
Duration: 3-7 days
Goal: collect baseline data
```

What to watch:
- How many requests would be blocked?
- What patterns are flagged?
- Are there false positives?
- What's the latency overhead?

Dashboard shows:
```
Requests:         12,450
Would-be-blocked: 23 (0.18%)
Would-be-redacted: 156 (1.25%)
Avg latency:      +8ms
False positives:  0
```

**Promotion criteria:**
- ✅ <1% false positive rate
- ✅ <50ms latency overhead
- ✅ No critical false positives
- ✅ 3+ days of data collected

> **How FP rate is computed:** From three sources: (a) **manual review labels** — operator marks a blocked/redacted event as "false positive" in UI, (b) **dismissed incidents** — incidents dismissed without action count as likely FPs, (c) **observed-but-allowed** — in observe mode, events where `would_block: true` but no downstream incident occurred. See [agents-v1.spec.md](../agents-v1.spec.md) Req 6.

### Week 2: Warn

```
Mode: warn
Duration: 3-7 days
Goal: validate alerts are meaningful
```

What changes:
- Same as observe, but now sends alerts
- Team gets notified of violations
- Violations are still allowed through

Review process:
1. Alert fires
2. Team reviews: real attack or false positive?
3. If false positive → adjust policy
4. If real → confirms enforcement will work

**Promotion criteria:**
- ✅ All alerts reviewed
- ✅ False positive rate < 0.5%
- ✅ No business-critical false positives
- ✅ Team confirms alert quality is good

### Week 3: Enforce

```
Mode: enforce
Duration: ongoing
Goal: active protection
```

What changes:
- Violations are now blocked
- PII is redacted in responses
- Unauthorized tool calls are rejected
- Budget limits are enforced

Monitoring:
- Watch for user complaints
- Monitor false positive reports
- Track blocked request rate
- Review traces for edge cases

**Optional escalation to strict (v2):**
- All policies stable for 30+ days
- No false positives for 14+ days
- High-risk agent (finance, HR, healthcare)
- Strict mode is planned for v2 — see [agents-v1.spec.md](../agents-v1.spec.md)

### Future (v2): Strict

> **Not in v1.** Documented here for planning purposes.

```
Mode: strict
Duration: for critical agents
Goal: maximum protection
```

What changes compared to enforce:
- Fail **closed** on errors (enforce fails open)
- Uncertain classifications → block (enforce → allow)
- Lower confidence thresholds
- Every gate decision is audited

Use this for:
- Financial transaction agents
- HR/employee data agents
- Healthcare agents
- Agents with regulatory compliance requirements

---

## Promotion API

### Manual promotion

```http
POST /api/agents/:id/promote
Content-Type: application/json

{
  "from": "observe",
  "to": "warn",
  "reason": "3 days clean, 0 false positives"
}
```

### Check promotion readiness

```http
GET /api/agents/:id/promotion-readiness

Response:
{
  "current_mode": "observe",
  "next_mode": "warn",
  "ready": true,
  "criteria": {
    "min_days": { "required": 3, "actual": 5, "met": true },
    "false_positive_rate": { "required": "< 1%", "actual": "0%", "met": true },
    "latency_overhead": { "required": "< 50ms", "actual": "8ms", "met": true },
    "critical_fp": { "required": 0, "actual": 0, "met": true }
  },
  "recommendation": "Safe to promote to warn"
}
```

### Rollback

```http
POST /api/agents/:id/rollback
Content-Type: application/json

{
  "from": "enforce",
  "to": "warn",
  "reason": "False positive affecting checkout flow"
}
```

---

## False positive management

When a legitimate request is blocked:

### 1. Identify

```json
{
  "event": "false_positive",
  "agent": "customer-support-copilot",
  "tool": "getOrderStatus",
  "input": "Order status for Dr. Ignore?",
  "blocked_by": "injection_detection",
  "pattern": "ignore.*instructions",
  "actual_intent": "legitimate customer name lookup"
}
```

### 2. Create exception

```yaml
# exceptions.yaml

exceptions:
  - id: "fp-001"
    created: "2025-01-15"
    pattern: "injection_detection"
    context: "Customer name containing 'ignore'"
    rule: |
      Allow when:
        - tool = getOrderStatus
        - arg 'order_id' matches ^ORD-\d+$
        - 'ignore' appears in customer name field, not in instructions
    expires: "2025-04-15"  # re-evaluate in 90 days
```

### 3. Re-validate

```bash
ai-protector validate --agent customer-support-copilot --include-exceptions
```

---

## Code integration

### Setting mode at startup

```python
from ai_protector import ProtectorConfig

config = ProtectorConfig(
    mode="observe",             # or from env: AI_PROTECTOR_MODE
    fail_open=True,             # allow on error (observe/warn)
    on_would_block=log_would_block,  # callback for observe mode
    on_warn=send_alert,              # callback for warn mode
)

pre_gate = PreToolGate(config=config, rbac=rbac, limits=limits)
post_gate = PostToolGate(config=config, pii=True, secrets=True)
```

### Mode-aware gate behavior

```python
# In observe mode:
decision = pre_gate.check(role="customer", tool="issueRefund", args={})
# decision.action = "WOULD_BLOCK"
# decision.enforced = False
# Tool call proceeds, decision is logged

# In enforce mode:
decision = pre_gate.check(role="customer", tool="issueRefund", args={})
# decision.action = "BLOCKED"
# decision.enforced = True
# Tool call is stopped
```

---

## UI implementation plan

### Screen: "Deployment"

**Route:** `/agents/:id/deploy`

```
┌───────────────────────────────────────────────────────────┐
│         Deploy: Customer Support Copilot                  │
│                                                           │
│  Current mode: OBSERVE                                    │
│  Running since: 5 days                                    │
│                                                           │
│  ┌──── Rollout progress ──────────────────────────────┐  │
│  │                                                     │  │
│  │  [■ Observe] → [ Warn ] → [ Enforce ]               │  │
│  │   ▲ current                                         │  │
│  │                                                     │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌──── Promotion readiness ───────────────────────────┐  │
│  │                                                     │  │
│  │  ✅ Min 3 days of data        5 / 3 days            │  │
│  │  ✅ False positive rate       0% / < 1%             │  │
│  │  ✅ Latency overhead          8ms / < 50ms          │  │
│  │  ✅ No critical FPs           0 found               │  │
│  │                                                     │  │
│  │  Status: READY TO PROMOTE                           │  │
│  │                                                     │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌──── Observe stats ─────────────────────────────────┐  │
│  │                                                     │  │
│  │  Total requests:      12,450                        │  │
│  │  Would-be-blocked:    23  (0.18%)                   │  │
│  │  Would-be-redacted:   156 (1.25%)                   │  │
│  │  Avg latency added:   +8ms                          │  │
│  │                                                     │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│   [ Promote to Warn → ]   [ Rollback ]                    │
│                                                           │
│       [ Continue → Monitor Traces ]                       │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## Next step

→ **Step 8** — [Monitor Traces & Incidents](08-traces-incidents.md)
