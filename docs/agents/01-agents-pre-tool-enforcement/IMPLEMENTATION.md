# Spec 01 — Pre-tool Enforcement Gate: Implementation Notes

> **Status:** Implemented  
> **Commit:** `c99c3be` on `feat/agents-mode`  
> **Tests:** 35 new (93 total, all passing)

---

## What Changed

### Before

```
tool_router → tool_executor → llm_call
```

`tool_executor` did one check — is the tool in `allowed_tools` for the role? If yes → execute. No argument inspection, no context analysis, no injection protection, no audit trail.

### After

```
tool_router → pre_tool_gate → tool_executor → llm_call
                   │
                   ├─ ALLOW → tool_executor (normal)
                   ├─ BLOCK → skip tool, record reason, go to LLM
                   ├─ MODIFY → sanitize args, then tool_executor
                   └─ REQUIRE_CONFIRMATION → return question to user, STOP
```

---

## 5-Check Pipeline (fail-fast)

For **every** proposed tool call, the gate runs checks sequentially. First failure = immediate decision.

| # | Check | What it does | Example block |
|---|-------|-------------|---------------|
| 1 | **RBAC** | Is the tool allowed for this role? | Customer → `getInternalSecrets` → BLOCK |
| 2 | **Arg injection** | 13 regex patterns in argument values | `"query": "ignore all previous instructions"` → BLOCK |
| 3 | **Context risk** | Exfiltration, injection in message, escalation | `"list all customer data"` + data tool → BLOCK |
| 4 | **Limits** | Has the session exceeded tool call limits? | 20+ calls in session → BLOCK |
| 5 | **Confirmation** | Does this tool require human approval? | (stub — ready for spec 02) |

---

## Files Modified / Created

| File | Change |
|------|--------|
| `src/agent/state.py` | Added `CheckResult`, `GateDecision` TypedDicts; added `gate_decisions`, `pending_confirmation` to `AgentState` |
| `src/agent/nodes/pre_tool_gate.py` | **NEW** (~290 lines) — gate node with 5 checks, 13 injection patterns, 5 exfiltration patterns, escalation detection |
| `src/agent/graph.py` | Rewired: `tool_router → pre_tool_gate → (conditional) → tool_executor / llm_call / confirmation_response` |
| `src/agent/nodes/tools.py` | `tool_executor_node` — RBAC check kept as defense-in-depth fallback |
| `tests/test_pre_tool_gate.py` | **NEW** — 35 tests covering all 4 decision paths |

---

## Detection Patterns

### Injection (13 patterns)
- `ignore (all) previous instructions`
- `you are now`
- `new system prompt`
- `reveal (your) (system) prompt`
- `disregard (all) (prior|previous|above)`
- `override (all) rules`
- `act as (an) unrestricted`
- `do anything now`
- `jailbreak`
- `<|im_start|>`
- `[INST]`
- `<<SYS>>`
- `### (system|assistant):`

### Exfiltration (5 patterns)
- `(list|show|get|dump|export) (all|every) (user|customer|record|data|secret|key|password)`
- `(enumerate|extract|download) ... (database|table|record)`
- `bulk (export|download|extract)`
- `SELECT * FROM`
- `(DROP|DELETE|TRUNCATE|ALTER) (TABLE|DATABASE)`

### Escalation
- 3+ blocked attempts in the same session → all subsequent tool calls blocked automatically.

### Payload size
- Arguments exceeding 2000 characters → blocked (payload bombing protection).

---

## Stubs (waiting for future specs)

| Stub | Waiting for |
|------|-------------|
| `TOOLS_REQUIRING_CONFIRMATION = set()` | Spec 02 — RBAC with `requires_confirmation` flag |
| `_check_args` — regex only | Spec 04 — Full Pydantic schema validation per tool |
| `_check_limits` — simple counter | Spec 06 — Redis rate limiting, token budgets |
| `MODIFY` path — never returned | Spec 04 — Argument sanitization (trim/normalize) |

---

## Data Flow

```python
# Input (from tool_router):
state["tool_plan"] = [
    {"tool": "getOrderStatus", "args": {"order_id": "ORD-001"}},
    {"tool": "getInternalSecrets", "args": {}},
]

# Output (from pre_tool_gate):
state["tool_plan"] = [
    {"tool": "getOrderStatus", "args": {"order_id": "ORD-001"}},
    # getInternalSecrets removed — BLOCKED by RBAC
]
state["gate_decisions"] = [
    {"tool": "getOrderStatus", "decision": "ALLOW", "risk_score": 0.0, ...},
    {"tool": "getInternalSecrets", "decision": "BLOCK", "reason": "not permitted for this role", "risk_score": 1.0, ...},
]
state["tool_calls"] = [
    # Blocked tool recorded with allowed=False
    {"tool": "getInternalSecrets", "args": {}, "result": "Blocked by pre-tool gate: ...", "allowed": False},
]
```
