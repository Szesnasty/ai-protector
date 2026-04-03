# Step 4 — Choose a Policy Pack

**Time: 5 minutes**
**Input: agent profile + RBAC config**
**Output: complete policy configuration tuned to your agent type**

---

## Why this step matters

A policy pack is a pre-built set of security thresholds, scanner
settings, budget limits, and redaction rules — calibrated for a
specific type of agent.

You don't create security policies from scratch.
You pick a pack that matches your agent type and adjust 2–3 knobs.

---

## Available policy packs

### Customer Support Agent

**Best for:** External-facing agents that answer questions, check orders,
and process simple transactions.

```yaml
pack: customer_support
risk_profile: medium-high

proxy:
  policy: balanced               # balanced between security and usability
  injection_threshold: 0.5
  pii_redaction: true
  secrets_scanning: true
  max_prompt_length: 8000
  blocked_categories: [jailbreak, toxicity, data_exfiltration]

agent:
  pre_tool_gate:
    rbac: strict                 # default-deny, role-based
    argument_validation: true    # Pydantic schemas + injection scan
    context_risk: true           # exfiltration + escalation detection
    max_tool_calls_per_request: 5
  post_tool_gate:
    pii_redaction: true          # redact emails, phones, SSN, etc.
    secrets_scanning: true       # strip API keys, tokens, passwords
    injection_scanning: true     # detect indirect prompt injection
    max_output_size: 4000
  confirmation:
    write_tools: true            # all write tools need human approval
    critical_tools: true         # critical sensitivity needs approval
  budgets:
    customer: { tool_calls: 20, tokens: 20000, cost: 0.50, rpm: 10 }
    support:  { tool_calls: 50, tokens: 50000, cost: 1.00, rpm: 20 }
    admin:    { tool_calls: 100, tokens: 100000, cost: 5.00, rpm: 60 }

rollout:
  initial_mode: observe
  promotion_after: 500_requests
```

---

### Internal Copilot

**Best for:** Internal employees using an AI assistant for productivity —
document search, ticket management, data queries.

```yaml
pack: internal_copilot
risk_profile: medium

proxy:
  policy: fast                   # lower latency, trusted users
  injection_threshold: 0.6      # slightly more permissive
  pii_redaction: false           # internal users can see PII
  secrets_scanning: true         # still block secrets
  max_prompt_length: 16000

agent:
  pre_tool_gate:
    rbac: standard               # role-based but fewer restrictions
    argument_validation: true
    context_risk: false          # lower risk, skip context heuristics
    max_tool_calls_per_request: 10
  post_tool_gate:
    pii_redaction: false         # internal users can see data
    secrets_scanning: true       # but never leak credentials
    injection_scanning: true
    max_output_size: 8000
  confirmation:
    write_tools: false           # trusted users, no confirmation for write
    critical_tools: true         # still confirm critical actions
  budgets:
    employee: { tool_calls: 100, tokens: 100000, cost: 5.00, rpm: 30 }
    admin:    { tool_calls: 200, tokens: 200000, cost: 20.00, rpm: 60 }

rollout:
  initial_mode: warn
  promotion_after: 200_requests
```

---

### Finance Agent

**Best for:** Agents that handle financial data, process payments,
access accounting systems, or generate reports with monetary values.

```yaml
pack: finance_agent
risk_profile: high

proxy:
  policy: strict                 # aggressive blocking
  injection_threshold: 0.3      # low threshold = more blocking (safer)
  pii_redaction: true
  secrets_scanning: true
  max_prompt_length: 4000       # shorter prompts = less attack surface

agent:
  pre_tool_gate:
    rbac: strict
    argument_validation: true
    context_risk: true
    max_tool_calls_per_request: 3  # very limited
  post_tool_gate:
    pii_redaction: true
    secrets_scanning: true
    injection_scanning: true
    max_output_size: 2000
  confirmation:
    write_tools: true
    critical_tools: true
    high_value_threshold: 1000   # confirm transactions > $1000
  budgets:
    viewer:   { tool_calls: 10, tokens: 10000, cost: 0.25, rpm: 5 }
    analyst:  { tool_calls: 30, tokens: 30000, cost: 1.00, rpm: 15 }
    admin:    { tool_calls: 50, tokens: 50000, cost: 5.00, rpm: 30 }

rollout:
  initial_mode: enforce          # finance = strict from day 1
  promotion_after: 0             # no observe period
```

---

### HR Agent

**Best for:** Agents that access employee data, handle leave requests,
process benefits, or answer HR policy questions.

```yaml
pack: hr_agent
risk_profile: high

proxy:
  policy: strict
  injection_threshold: 0.4
  pii_redaction: true            # critical — employee PII everywhere
  secrets_scanning: true
  max_prompt_length: 8000
  blocked_categories: [jailbreak, toxicity, data_exfiltration, discrimination]

agent:
  pre_tool_gate:
    rbac: strict
    argument_validation: true
    context_risk: true
    max_tool_calls_per_request: 5
  post_tool_gate:
    pii_redaction: true          # always redact PII in non-admin responses
    secrets_scanning: true
    injection_scanning: true
    max_output_size: 4000
    field_masking:               # role-dependent disclosure
      employee:
        - { field: "salary", action: "hide" }
        - { field: "ssn", action: "hide" }
        - { field: "email", action: "mask" }
      hr_admin:
        - { field: "salary", action: "allow" }
        - { field: "ssn", action: "mask" }
  confirmation:
    write_tools: true
    critical_tools: true
  budgets:
    employee: { tool_calls: 15, tokens: 15000, cost: 0.50, rpm: 10 }
    hr_admin: { tool_calls: 50, tokens: 50000, cost: 2.00, rpm: 20 }

rollout:
  initial_mode: enforce
  promotion_after: 0
```

---

### Read-only Research Agent

**Best for:** RAG agents that only search documents and answer questions.
No tools, no write actions, no PII.

```yaml
pack: readonly_research
risk_profile: low

proxy:
  policy: fast
  injection_threshold: 0.6
  pii_redaction: false
  secrets_scanning: false
  max_prompt_length: 16000

agent:
  pre_tool_gate:
    rbac: standard
    argument_validation: true
    context_risk: false
    max_tool_calls_per_request: 10
  post_tool_gate:
    pii_redaction: false
    secrets_scanning: false
    injection_scanning: true     # still check for indirect injection
    max_output_size: 8000
  confirmation:
    write_tools: false
    critical_tools: false
  budgets:
    user: { tool_calls: 50, tokens: 100000, cost: 2.00, rpm: 30 }

rollout:
  initial_mode: warn
  promotion_after: 100_requests
```

---

## Customization knobs

Every pack can be adjusted. The most common knobs:

| Knob | What it controls | Range |
|------|-----------------|-------|
| **Proxy policy** | How strict prompt scanning is | `fast` / `balanced` / `strict` / `paranoid` |
| **Injection threshold** | Score above which prompts are blocked | 0.0 (block everything) – 1.0 (allow everything) |
| **PII redaction** | Whether PII is redacted in tool output | on / off |
| **Confirmation rules** | Which actions need human approval | per sensitivity level |
| **Session budgets** | Cost, tokens, tool calls per session | per role |
| **Rollout mode** | How strictly policies are enforced | observe / warn / enforce / strict |

### When to adjust

| Symptom | Adjustment |
|---------|------------|
| Too many false positives | Raise `injection_threshold` from 0.3 → 0.5 |
| Attacks getting through | Lower `injection_threshold` from 0.6 → 0.4 |
| Users hitting limits too fast | Raise `budgets` for that role |
| Agent too slow | Switch from `strict` → `balanced` policy |
| Sensitive data leaking | Enable `pii_redaction` + lower `max_output_size` |

---

## Pack comparison

| Feature | Support | Internal | Finance | HR | Research |
|---------|---------|----------|---------|-----|----------|
| Proxy policy | balanced | fast | strict | strict | fast |
| PII redaction | ✅ | ❌ | ✅ | ✅ | ❌ |
| Write confirmation | ✅ | ❌ | ✅ | ✅ | ❌ |
| Context risk | ✅ | ❌ | ✅ | ✅ | ❌ |
| Field masking | ❌ | ❌ | ❌ | ✅ | ❌ |
| Customer budget | $0.50 | — | $0.25 | $0.50 | $2.00 |
| Initial rollout | observe | warn | enforce | enforce | warn |
| Best for risk | medium | medium | high | high | low |

---

## UI implementation plan

### Screen: "Choose Protection"

**Route:** `/agents/:id/policy`

```
┌───────────────────────────────────────────────────────────┐
│         Choose a policy pack                              │
│                                                           │
│  Based on your agent profile:                             │
│  Risk: HIGH · External · Uses tools · Write actions · PII │
│                                                           │
│  ┌─────────────────────────────┐  ┌────────────────────┐  │
│  │  ★ Customer Support Agent   │  │  Internal Copilot  │  │
│  │  ────────────────────────── │  │  ────────────────  │  │
│  │  ✓ RBAC strict              │  │  RBAC standard     │  │
│  │  ✓ PII redaction            │  │  No PII redaction   │  │
│  │  ✓ Write confirmation       │  │  No confirmation    │  │
│  │  ✓ Context risk detection   │  │  Context risk off   │  │
│  │  ✓ $0.50 customer budget    │  │  $5.00 budget       │  │
│  │                             │  │                    │  │
│  │  [ Use This Pack ]  ← rec  │  │  [ Use This Pack ] │  │
│  └─────────────────────────────┘  └────────────────────┘  │
│                                                           │
│  ┌─────────────────────────────┐  ┌────────────────────┐  │
│  │  Finance Agent              │  │  HR Agent           │  │
│  │  ────────────────────────── │  │  ──────────────    │  │
│  │  RBAC strict                │  │  RBAC strict        │  │
│  │  PII + secrets redaction    │  │  PII + field mask   │  │
│  │  All confirmation           │  │  All confirmation   │  │
│  │  $0.25 viewer budget        │  │  $0.50 emp budget   │  │
│  │                             │  │                    │  │
│  │  [ Use This Pack ]          │  │  [ Use This Pack ] │  │
│  └─────────────────────────────┘  └────────────────────┘  │
│                                                           │
│              [ ⚙ Create Custom Pack ]                     │
│                                                           │
│       [ Continue → Generate Integration Kit ]             │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## Next step

→ **Step 5** — [Generate Integration Kit](05-integration-kit.md)
