# Protect Your Agent — Implementation Roadmap

**Register your agent, map its tools and roles, generate deterministic guardrails,
validate them with attack tests, and roll them out safely.**

---

## The problem

You have an agent. It calls tools. You're worried about:

- Prompt injection making it call `deleteAllRecords`
- Tool output leaking PII or secrets to the user
- A customer-role user tricking it into admin actions
- Runaway loops burning $500 in API costs
- No visibility into what the agent actually did

You don't want to study architecture docs.
You want your agent safe in 30–60 minutes.

---

## The flow

AI Protector solves this in 8 steps — not 8 weeks.

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   1. Describe Agent  →  risk profile + recommended preset   │
│   2. Register Tools  →  name, access, sensitivity, schema   │
│   3. Map Roles       →  RBAC config generated for you       │
│   4. Choose Policy   →  preset pack, tuned to your type     │
│   5. Generate Kit    →  copy-paste code, config, env vars   │
│   6. Run Validation  →  attack tests against your setup     │
│   7. Deploy Safely   →  observe → warn → enforce            │
│   8. Monitor Live    →  traces, incidents, blocked calls     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Each step has a dedicated guide. Start at step 1 — you'll have a
protected agent by step 5.

---

## Guides

| Step | Guide | What you get | Time |
|------|-------|-------------|------|
| 1 | [Describe Your Agent](01-describe-agent.md) | Risk profile, recommended protection level | 5 min |
| 2 | [Register Tools](02-register-tools.md) | Tool registry with access, sensitivity, schema | 10 min |
| 3 | [Generate RBAC](03-generate-rbac.md) | `rbac.yaml` with roles, inheritance, default-deny | 10 min |
| 4 | [Choose a Policy Pack](04-policy-packs.md) | Pre-built preset for your agent type | 5 min |
| 5 | [Generate Integration Kit](05-integration-kit.md) | 7 files: config, wrapper, env, tests, README | 15 min |
| 6 | [Run Attack Validation](06-attack-validation.md) | Security test suite tailored to your agent | 10 min |
| 7 | [Deploy with Rollout Modes](07-rollout-modes.md) | Observe → Warn → Enforce progression | 5 min |
| 8 | [Monitor Traces & Incidents](08-traces-incidents.md) | Live visibility into every decision | ongoing |

**Total: ~60 minutes from zero to protected agent.**

---

## What you need

- Python 3.11+
- Your existing agent (LangGraph, CrewAI, AutoGen, raw Python, or any framework)
- Docker (for proxy mode) or `pip install` (for library mode)

```bash
pip install pydantic pyyaml structlog
```

---

## Three protection levels

Not every agent needs every layer. Choose what fits:

| Level | What it does | Best for | Setup time |
|-------|-------------|----------|------------|
| **Proxy only** | Firewall between app and LLM — scans prompts and responses | Simple chat, RAG, no tools | 5 min |
| **Agent runtime** | Pre/post-tool gates inside your agent graph | Tool-calling agents | 30 min |
| **Full protection** | Proxy + agent runtime + tracing + budgets | Production agents with sensitive tools | 60 min |

After step 1, you'll know which level fits your agent.

---

## The "magic moment"

The strongest moment isn't when you see a dashboard.

It's when you:
1. Register your agent and tools
2. Generate the integration kit
3. Paste the snippet into your code
4. Fire a prompt injection attack
5. See: **BLOCKED** — with full explanation

That's when you understand the value.

---

## Quick start — minimum viable protection

If you only implement ONE thing, do this:

```python
# rbac.yaml
roles:
  user:
    tools:
      searchProducts: { scopes: [read], sensitivity: low }
  admin:
    inherits: user
    tools:
      deleteRecord: { scopes: [write], sensitivity: critical, requires_confirmation: true }
```

```python
from ai_protector import RBACService, post_tool_scan

rbac = RBACService("rbac.yaml")

def handle_tool_call(role: str, tool: str, args: dict) -> str:
    # Check permission
    perm = rbac.check_permission(role, tool)
    if not perm.allowed:
        return f"Access denied: {perm.reason}"

    # Execute tool
    result = execute_tool(tool, args)

    # Scan output
    return post_tool_scan(result)
```

30 lines. Your agent is already safer than 95% of deployed agents.

Now follow the guides for the full protection stack →

---

## v1 specification

The formal requirements, Definition of Done, and implementation order
for shipping Agents as a product pillar:

→ **[agents-v1.spec.md](../agents-v1.spec.md)**

---

## Engineering plan (specs 26–33)

Each step has a SPEC.md with sub-steps, DoD checklists, and effort estimates.
Build order is sequential — each step depends on the previous.

| Step | Spec | Sub-steps | Effort |
|------|------|-----------|--------|
| 26 | [Agent CRUD](../plan/26-aw-agent-crud/SPEC.md) | 26a–26d: DB model, risk classification, CRUD API, seed data | 2 days |
| 27 | [Tools & Roles CRUD](../plan/27-aw-tools-roles-crud/SPEC.md) | 27a–27d: Tool CRUD, Role CRUD, permission matrix, seed data | 2 days |
| 28 | [Config Generation](../plan/28-aw-config-generation/SPEC.md) | 28a–28e: rbac.yaml, limits.yaml, policy packs, policy.yaml, API | 2 days |
| 29 | [Integration Kit](../plan/29-aw-integration-kit/SPEC.md) | 29a–29l: Jinja2 templates, framework wrappers, tests, download API | 3 days |
| 30 | [Validation Runner](../plan/30-aw-validation-runner/SPEC.md) | 30a–30d: test pack, engine, API, determinism properties | 2 days |
| 31 | [Rollout Modes](../plan/31-aw-rollout-modes/SPEC.md) | 31a–31e: DB enum, gate behavior, promotion API, traces, readiness | 2 days |
| 32 | [Traces & Incidents](../plan/32-aw-traces-persistence/SPEC.md) | 32a–32e: trace model, incidents, recorder, API, stats | 2 days |
| 33 | [Wizard UI](../plan/33-aw-wizard-ui/SPEC.md) | 33a–33l: sidebar, list, stepper, 7 wizard steps, detail page, composables | 4–5 days |

**Total: ~19–20 days of focused work.**

Critical path: 26 → 27 → 28 → 29 → 30 → 31 → 32 → 33

---

## Deep-dive reference

The existing technical guides cover each mechanism in detail:

| Topic | Reference | Source code |
|-------|-----------|-------------|
| RBAC internals | [RBAC & Tool Allowlist](ref/01-rbac.md) | `apps/agent-demo/src/agent/rbac/` |
| Pre-tool gate checks | [Pre-tool Gate](ref/02-pre-tool-gate.md) | `apps/agent-demo/src/agent/nodes/pre_tool_gate.py` |
| Post-tool gate scanners | [Post-tool Gate](ref/03-post-tool-gate.md) | `apps/agent-demo/src/agent/nodes/post_tool_gate.py` |
| Argument validation | [Argument Validation](ref/04-argument-validation.md) | `apps/agent-demo/src/agent/validation/` |
| Limits & budgets | [Limits & Budgets](ref/05-limits-budgets.md) | `apps/agent-demo/src/agent/limits/` |

These are for people who want to understand the internals.
The onboarding guides (steps 1–8) are for people who want to ship.
