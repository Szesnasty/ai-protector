# Agent Security — Implementation Guide

**Add deterministic security to any LLM agent in under an hour.**

This guide shows how to protect your agent using the same patterns
running in the AI Protector Agent Demo (421 tests, 9 security specs).

---

## The problem

When an LLM agent has access to tools (database queries, API calls,
email sending, file operations), every tool call is an attack surface:

- **Prompt injection** → agent calls `deleteAllRecords` because the user said "ignore instructions"
- **Data leakage** → tool returns PII/secrets, LLM echoes them to the user
- **Excessive agency** → agent loops and burns $500 in API costs
- **Privilege escalation** → customer-role user tricks agent into calling admin tools

The LLM can't be trusted to judge its own security.
Enforcement must be **deterministic and external to the model**.

---

## Architecture

Two hooks — one before the tool runs, one after:

```
User message
     │
     ▼
┌─────────────────┐
│  Intent + RBAC  │  →  Which tools can this role use?
└────────┬────────┘
         ▼
┌─────────────────┐
│  PRE-TOOL GATE  │  →  RBAC ✓  Args ✓  Context ✓  Limits ✓  Confirmation ✓
└────────┬────────┘
         │  ALLOW / BLOCK / MODIFY / REQUIRE_CONFIRMATION
         ▼
┌─────────────────┐
│  TOOL EXECUTOR  │  →  Runs the actual tool
└────────┬────────┘
         ▼
┌─────────────────┐
│ POST-TOOL GATE  │  →  PII ✓  Secrets ✓  Injection ✓  Size ✓
└────────┬────────┘
         │  PASS / REDACT / BLOCK
         ▼
┌─────────────────┐
│    LLM CALL     │  →  LLM sees only sanitized data
└────────┬────────┘
         ▼
     Response
```

---

## Guides

Each guide is self-contained. Start with #1, add layers as needed.

| # | Guide | What it does | Time |
|---|-------|-------------|------|
| 1 | [RBAC & Tool Allowlist](01-rbac.md) | Define roles, tools, and permissions in YAML. Default-deny. | 15 min |
| 2 | [Pre-tool Gate](02-pre-tool-gate.md) | Block unauthorized / malicious tool calls before execution. | 20 min |
| 3 | [Post-tool Gate](03-post-tool-gate.md) | Scan tool output for PII, secrets, injection before LLM sees it. | 15 min |
| 4 | [Argument Validation](04-argument-validation.md) | Pydantic schemas + injection scanning per tool. | 15 min |
| 5 | [Limits & Budgets](05-limits-budgets.md) | Per-role caps on tool calls, tokens, cost, rate. | 10 min |
| 6 | [Confirmation Flows](06-confirmation-flows.md) | Human-in-the-loop for sensitive actions. | 10 min |
| 7 | [Trace & Observability](07-trace.md) | Full evidence trail per request — what happened, what was blocked. | 15 min |
| 8 | [Role Separation](08-role-separation.md) | Anti-spoofing: delimiters, sanitization, safe message building. | 10 min |
| 9 | [Full Integration Example](09-full-example.md) | Complete working agent with all protections wired together. | 30 min |

**Total:** ~2.5 hours from zero to fully protected agent.

---

## What you need

- Python 3.11+
- `pydantic >= 2.0` (argument validation)
- `pyyaml` (RBAC config)
- `structlog` (logging, optional)
- Your existing agent framework (LangGraph, CrewAI, AutoGen, or raw code)

```bash
pip install pydantic pyyaml structlog
```

---

## Key principles

1. **Default-deny** — if a (role, tool) pair is not configured → BLOCK
2. **Deterministic** — no LLM-as-judge; rules, regex, thresholds only
3. **Defense in depth** — pre-tool gate + post-tool gate; each catches what the other can't
4. **Fail-fast** — pre-tool checks run in order; first failure = BLOCK
5. **LLM sees only sanitized data** — raw tool output never reaches the model
6. **Everything traced** — every decision recorded with reason and evidence

---

## Framework compatibility

The patterns in this guide are **framework-agnostic**. Two functions is
all you need:

```python
# Before tool execution
decision = pre_tool_check(role, tool_name, args, session)
if decision.blocked:
    return decision.reason

# Execute tool
result = my_tool(**args)

# After tool execution
sanitized = post_tool_scan(result)

# LLM sees only sanitized result
```

Examples are shown for:
- **LangGraph** (graph nodes)
- **Raw Python** (function calls)
- **Any framework** (middleware / decorator pattern)

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

# In your agent
from ai_protector_patterns import RBACService, post_tool_scan

rbac = RBACService("rbac.yaml")

def handle_tool_call(role: str, tool: str, args: dict) -> str:
    # Pre-check
    perm = rbac.check_permission(role, tool)
    if not perm.allowed:
        return f"Access denied: {perm.reason}"

    # Execute
    result = execute_tool(tool, args)

    # Post-scan
    sanitized = post_tool_scan(result)
    return sanitized
```

30 lines. Your agent is already safer than 95% of deployed agents.

Now read the guides for the full protection stack →

---

## Reference implementation

The complete working code lives in:

```
apps/agent-demo/src/agent/
├── rbac/                  # RBAC service + YAML config (Guide 1)
├── nodes/
│   ├── pre_tool_gate.py   # Pre-tool enforcement (Guide 2)
│   └── post_tool_gate.py  # Post-tool enforcement (Guide 3)
├── validation/            # Argument validation (Guide 4)
├── limits/                # Budgets & rate limits (Guide 5)
├── security/              # Sanitizer + message builder (Guide 8)
├── trace/                 # Observability (Guide 7)
├── tools/                 # Tool registry + implementations
├── graph.py               # LangGraph wiring
└── state.py               # Shared state definition
```
