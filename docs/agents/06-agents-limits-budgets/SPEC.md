# 06 — Limits: Rate Limiting / Iteration Caps / Budget Caps

> **Priority:** 6
> **Depends on:** 02 (RBAC — for per-role limits)
> **Used by:** 01 (Pre-tool Gate)
> **Sprint:** 3
> **Status:** ✅ Implemented — `c0acb8b`

---

## 1. Goal

Protect against **Denial-of-Wallet** and **agent loops** (attack or bug) that generate unbounded costs and system load. Without limits, a single malicious or buggy session can:
- Loop the agent indefinitely (infinite ReAct cycles)
- Call expensive tools hundreds of times
- Burn token budgets
- Overwhelm downstream services

---

## 2. Current State

Today in `agent-demo`:
- `iterations` counter exists in `AgentState` but is only incremented, never checked against a limit
- No max tool calls per session
- No token budget tracking
- No rate limiting per user/API key
- A prompt injection that triggers the agent to loop would run until LLM timeout

---

## 3. Limit Types

### 3.1. Iteration Caps

| Limit | Scope | Default | Description |
|-------|-------|---------|-------------|
| `max_iterations` | per request | 5 | Max ReAct loop cycles per single user message |
| `max_tool_calls_per_request` | per request | 10 | Max tool invocations per single user message |
| `max_tool_calls_per_session` | per session | 50 | Max tool invocations across entire conversation |
| `max_turns_per_session` | per session | 100 | Max user messages in a session |

### 3.2. Token/Cost Budgets

| Limit | Scope | Default | Description |
|-------|-------|---------|-------------|
| `max_tokens_per_request` | per request | 8192 | Max total tokens (prompt + completion) per LLM call |
| `max_tokens_per_session` | per session | 50000 | Max cumulative tokens across session |
| `max_cost_per_session` | per session | $1.00 | Estimated cost cap (based on token pricing) |

### 3.3. Rate Limits

| Limit | Scope | Default | Description |
|-------|-------|---------|-------------|
| `max_requests_per_minute` | per user | 20 | Rate limit per user per minute |
| `max_requests_per_hour` | per user | 200 | Rate limit per user per hour |
| `max_concurrent_sessions` | per user | 3 | Max simultaneous active sessions |

### 3.4. Per-Role Overrides

Limits can differ by role:

| Role | `max_iterations` | `max_tool_calls_session` | `max_tokens_session` |
|------|------------------|--------------------------|----------------------|
| `customer` | 3 | 20 | 20000 |
| `support` | 5 | 50 | 50000 |
| `admin` | 10 | 100 | 100000 |

---

## 4. How It Works

### 4.1. Check Points

Limits are checked at **four points** in the agent flow:

```
1. Request entry (input_node)
   └─ rate limit check (requests/min, concurrent sessions)

2. Pre-tool gate (before each tool call)
   └─ iteration cap, tool call count, token budget

3. Post-LLM call (after llm_call_node)
   └─ token usage accumulation, cost estimation

4. Loop continuation check (before next iteration)
   └─ iteration cap, total tool calls
```

### 4.2. On Limit Exceeded

When any limit is hit:

1. Agent stops the current operation.
2. Sets `final_response` to a safe completion message:
   ```
   "I've reached the maximum number of operations for this request.
    Please try a more specific question or start a new conversation."
   ```
3. Logs the event:
   ```json
   {
     "event": "limit_exceeded",
     "limit_type": "max_tool_calls_per_session",
     "limit_value": 50,
     "current_value": 51,
     "session_id": "...",
     "user_role": "customer"
   }
   ```
4. Records `limit_exceeded` in agent trace.
5. Session can continue for new messages but with a warning flag.

### 4.3. Token Tracking

After each LLM call:
- Extract `prompt_tokens` and `completion_tokens` from response
- Add to session counters: `session_tokens_in`, `session_tokens_out`
- Estimate cost: `tokens * price_per_token` (configurable per model)
- Check against `max_tokens_per_session` and `max_cost_per_session`

### 4.4. Rate Limiting (Redis)

Use Redis sliding window:
- Key: `rate:{user_id}:{window}` (e.g. `rate:user123:minute`)
- On each request: `INCR` + `EXPIRE` (TTL = window size)
- If count > limit → reject with 429 status

---

## 5. Data Structures

### 5.1. LimitsConfig

```python
class LimitsConfig(TypedDict):
    max_iterations: int
    max_tool_calls_per_request: int
    max_tool_calls_per_session: int
    max_turns_per_session: int
    max_tokens_per_request: int
    max_tokens_per_session: int
    max_cost_per_session: float
    max_requests_per_minute: int
    max_requests_per_hour: int
    max_concurrent_sessions: int
```

### 5.2. AgentState Additions

```python
class AgentState(TypedDict, total=False):
    # ... existing fields ...

    # Counters (NEW)
    session_tool_calls: int       # Cumulative tool calls in session
    session_tokens_in: int        # Cumulative input tokens
    session_tokens_out: int       # Cumulative output tokens
    session_estimated_cost: float # Estimated $ cost
    session_turns: int            # Number of user messages

    # Limit state (NEW)
    limits_config: LimitsConfig
    limit_exceeded: str | None    # Which limit was hit (None = OK)
```

---

## 6. Implementation Steps

- [x] **6a.** Define `LimitsConfig` data structure
- [x] **6b.** Create `src/agent/limits/service.py` with `check_limits()`, `update_counters()`
- [x] **6c.** Create default limits config per role (in RBAC config from point 2)
- [x] **6d.** Implement iteration cap check in agent graph loop
- [x] **6e.** Implement tool call counter (per request + per session)
- [x] **6f.** Implement token tracking after LLM calls
- [x] **6g.** Implement cost estimation (tokens × price)
- [x] **6h.** Implement rate limiting with Redis sliding window
- [x] **6i.** Implement safe completion response when limit hit
- [x] **6j.** Integrate limit checks into `pre_tool_gate` (point 1)
- [x] **6k.** Integrate limit checks into `input_node` (rate limits)
- [x] **6l.** Add limit events to agent trace
- [x] **6m.** Write tests: each limit type is enforced correctly
- [x] **6n.** Write tests: per-role overrides work
- [x] **6o.** Write tests: safe completion message on limit exceeded

---

## 7. Test Scenarios

| Scenario | Expected |
|----------|----------|
| 6th iteration when `max_iterations=5` | Agent stops, safe completion message |
| 11th tool call in request when `max_tool_calls_per_request=10` | BLOCK in pre-tool gate |
| 51st tool call in session when `max_tool_calls_per_session=50` | BLOCK in pre-tool gate |
| Token count exceeds session budget | Agent stops after LLM call |
| 21st request in a minute for user with `max_requests_per_minute=20` | 429 at input |
| Admin with higher limits reaches customer's limit | Still running (admin has higher cap) |
| Infinite loop attack (injection causes agent to keep calling tools) | Stops at `max_iterations` |

---

## 8. Definition of Done

- [x] Iteration caps enforced (per request, per session)
- [x] Tool call limits enforced (per request, per session)
- [x] Token budget tracked and enforced per session
- [x] Cost estimation works per session
- [x] Rate limiting works per user (Redis)
- [x] Per-role limit overrides work
- [x] Safe completion message on limit exceeded
- [x] All limit events logged and added to trace
- [x] Infinite loop attacks are capped
- [x] Tests pass for all limit types
