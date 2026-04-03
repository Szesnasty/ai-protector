# 01 — Pre-tool Enforcement (Gate Before Tool Execution)

> **Priority:** 1 (most critical)
> **Depends on:** 02 (RBAC), 04 (Arg Validation), 06 (Limits)
> **Sprint:** 1
> **Status:** ✅ Implemented — `c99c3be`
>
> **Note on dependencies:** Points 01, 02, and 04 are developed in **parallel** during Sprint 1.
> The pre-tool gate defines **interfaces** (e.g. `check_tool_permission()`, `validate_tool_args()`)
> that 02 and 04 implement. During development, stubs return `ALLOW` by default — the gate
> structure and wiring are built first, then checks are connected as they become available.
> Point 06 (Limits) is Sprint 3 — the gate includes a limit check hook that is a no-op until then.

---

## 1. Goal

Prevent the agent from performing irreversible actions or exfiltrating data before you can react. This is the single most important control in agentic systems.

**Why first:** without a pre-tool gate, the agent executes every tool call the model proposes — including malicious ones injected via prompt injection, jailbreak, or social engineering. By the time you check the output (post-tool, point 3), the damage (API call, DB write, data exfiltration) is already done.

---

## 2. Current State

Today in `agent-demo`, the flow is:

```
tool_router_node → tool_executor_node → llm_call_node
```

`tool_executor_node` does a simple allowlist check (`if tool_name not in allowed`) but:
- No argument inspection
- No intent/context analysis
- No conversation-level risk assessment
- No REQUIRE_CONFIRMATION path
- Decision is not logged to trace

---

## 3. Target Architecture

```
tool_router_node
       │
       ▼
┌──────────────┐
│ pre_tool_gate│  For EACH proposed tool call:
│              │
│  1. RBAC check (from 02-rbac-allowlist)
│  2. Argument validation (from 04-argument-validation)
│  3. Context risk assessment
│  4. Limit check (from 06-limits-budgets)
│  5. Decision: ALLOW | BLOCK | MODIFY | REQUIRE_CONFIRMATION
│              │
└──────┬───────┘
       │
       ├─ ALLOW ──────────▶ tool_executor_node
       ├─ BLOCK ──────────▶ skip tool, add block record to trace
       ├─ MODIFY ─────────▶ sanitize args, then tool_executor_node
       └─ REQUIRE_CONFIRM ▶ pause, ask user, resume on approval
```

---

## 4. How It Works (Step by Step)

### 4.1. Input

The gate receives from `tool_router_node`:
- `tool_plan`: list of `{"tool": name, "args": {...}}` — proposed tool calls
- Full `AgentState` (including `user_role`, `chat_history`, `intent`, `allowed_tools`)

### 4.2. Per-tool evaluation

For **each** tool call in `tool_plan`, the gate runs these checks in order (fail-fast):

| # | Check | Source | On fail |
|---|-------|--------|---------|
| 1 | **RBAC allowlist** | `02-rbac-allowlist` | BLOCK — tool not permitted for role |
| 2 | **Scope check** | `02-rbac-allowlist` | BLOCK — e.g. write scope not granted |
| 3 | **Argument schema** | `04-argument-validation` | BLOCK or MODIFY — invalid/suspicious args |
| 4 | **Context risk** | local heuristics | BLOCK — conversation suggests exfiltration/injection |
| 5 | **Rate/budget limits** | `06-limits-budgets` | BLOCK — limits exceeded |
| 6 | **Requires confirmation?** | `02-rbac-allowlist` | REQUIRE_CONFIRMATION — sensitive tool |

### 4.3. Context Risk Assessment

This is the gate's own intelligence — not just RBAC:

- **Exfiltration signals:** user asks "list all users" or "export data" combined with a data-returning tool → elevate risk
- **Injection signals:** tool args contain instruction-like patterns (`ignore previous`, `you are now`, etc.)
- **Escalation signals:** repeated blocked attempts in the same session → raise suspicion
- **Volume signals:** too many tool calls proposed in one turn → suspicious

Implementation: rule-based heuristics first, optionally ML Judge later.

### 4.4. Decision

| Decision | Meaning | Action |
|----------|---------|--------|
| `ALLOW` | Tool call is safe | Execute tool |
| `BLOCK` | Tool call is denied | Skip tool, record reason, continue to next tool or LLM |
| `MODIFY` | Args need sanitization | Sanitize args (trim, normalize), then execute |
| `REQUIRE_CONFIRMATION` | Sensitive tool, needs human approval | Pause agent, return confirmation request to user |

### 4.5. Output

The gate updates `AgentState` with:
- `tool_plan` — filtered/modified (only ALLOW/MODIFY tools remain)
- `gate_decisions` — list of `{tool, decision, reason, checks_passed, checks_failed}`
- `tool_calls` — blocked tools added with `allowed: false` and reason

---

## 5. Data Structures

### 5.1. GateDecision

```python
class GateDecision(TypedDict):
    tool: str
    args: dict[str, Any]
    decision: Literal["ALLOW", "BLOCK", "MODIFY", "REQUIRE_CONFIRMATION"]
    reason: str | None
    checks: list[CheckResult]
    modified_args: dict[str, Any] | None  # Only if MODIFY
    risk_score: float  # 0.0–1.0 for this specific tool call

class CheckResult(TypedDict):
    check: str  # "rbac", "scope", "schema", "context_risk", "limits", "confirmation"
    passed: bool
    detail: str | None
```

### 5.2. AgentState additions

```python
class AgentState(TypedDict, total=False):
    # ... existing fields ...
    gate_decisions: list[GateDecision]  # NEW: per-tool gate outcomes
    pending_confirmation: dict | None    # NEW: tool awaiting user approval
```

---

## 6. Agent Graph Changes

### Before:
```
tool_router → tool_executor → llm_call
```

### After:
```
tool_router → pre_tool_gate → tool_executor → llm_call
                  │
                  └─ (if REQUIRE_CONFIRMATION) → END (return to user with confirmation request)
```

New conditional edge after `pre_tool_gate`:
- If any tool requires confirmation → route to `confirmation_response` node → END
- If all tools resolved (ALLOW/BLOCK/MODIFY) → route to `tool_executor`
- If all tools BLOCKED → skip `tool_executor`, go to `llm_call` (model answers without tools)

---

## 7. Implementation Steps

- [x] **7a.** Define `GateDecision` and `CheckResult` data structures in `state.py`
- [x] **7b.** Create `src/agent/nodes/pre_tool_gate.py` with the gate node function
- [x] **7c.** Implement RBAC check (calls into RBAC service from point 2)
- [x] **7d.** Implement argument quick-check (basic pattern detection — full validation in point 4)
- [x] **7e.** Implement context risk heuristics (exfiltration, injection, escalation signals)
- [x] **7f.** Implement limits check (delegate to limits service from point 6)
- [x] **7g.** Wire `pre_tool_gate` into agent graph between `tool_router` and `tool_executor`
- [x] **7h.** Add conditional edge for `REQUIRE_CONFIRMATION` path
- [x] **7i.** Update `tool_executor_node` to respect `gate_decisions` (skip BLOCKED tools)
- [x] **7j.** Add gate decisions to agent trace
- [x] **7k.** Write tests: ALLOW/BLOCK/MODIFY/REQUIRE_CONFIRMATION paths
- [x] **7l.** Write tests: context risk detection scenarios

---

## 8. Test Scenarios

| Scenario | Expected |
|----------|----------|
| Customer calls `getOrderStatus` with valid args | ALLOW |
| Customer calls `getInternalSecrets` | BLOCK (RBAC) |
| Admin calls `getInternalSecrets` | ALLOW |
| Tool args contain `ignore previous instructions` | BLOCK (context risk / arg check) |
| 10th tool call in a session (limit = 10) | BLOCK (limits) |
| Admin calls `refund(amount=99999)` (sensitive tool) | REQUIRE_CONFIRMATION |
| Tool args have SQL injection pattern | BLOCK (arg check) |
| Repeated blocked attempts in same session | BLOCK (escalation signal) |

---

## 9. Definition of Done

- [x] `pre_tool_gate` node exists and is wired into agent graph
- [x] Gate runs RBAC, arg check, context risk, limits checks
- [x] ALLOW → tool executes normally
- [x] BLOCK → tool is skipped, reason recorded in trace
- [x] MODIFY → args are sanitized before execution
- [x] REQUIRE_CONFIRMATION → agent pauses and asks user
- [x] All gate decisions are recorded in `gate_decisions` on state
- [x] Tests pass for all 4 decision paths
- [x] Context risk catches at least: exfiltration, injection in args, escalation
