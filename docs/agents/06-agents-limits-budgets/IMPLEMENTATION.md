# 06 — Limits: Rate Limiting / Iteration Caps / Budget Caps — Implementation Notes

> **Branch:** `feat/agents-mode`  
> **Date:** 2025-03-05

---

## 1. What Changed

### Before (Spec 05 baseline)

- `pre_tool_gate` had a stub `_check_limits()` with hardcoded `MAX_TOOL_CALLS_PER_SESSION = 20`
- No per-role limits
- No token tracking or cost estimation
- No rate limiting
- No turn counting
- `iterations` counter in state was never checked against a cap

### After (Spec 06)

A dedicated limits module with per-role configuration, session counters, token/cost budgets, and sliding-window rate limiting:

```
src/agent/limits/
├── __init__.py
├── config.py     # LimitsConfig dataclass, per-role defaults, get_limits_for_role()
└── service.py    # LimitsService singleton: counters, token tracking, rate limiter
```

---

## 2. New Modules

### `limits/config.py`

**`LimitsConfig`** — frozen dataclass with 10 limit fields:
- Per-request: `max_iterations`, `max_tool_calls_per_request`
- Per-session: `max_tool_calls_per_session`, `max_turns_per_session`
- Token/cost: `max_tokens_per_request`, `max_tokens_per_session`, `max_cost_per_session`
- Rate: `max_requests_per_minute`, `max_requests_per_hour`

**`ROLE_LIMITS`** — per-role overrides:

| Limit | Customer | Support | Admin |
|---|---|---|---|
| `max_iterations` | 3 | 5 | 10 |
| `max_tool_calls_per_request` | 5 | 10 | 20 |
| `max_tool_calls_per_session` | 20 | 50 | 100 |
| `max_turns_per_session` | 50 | 100 | 200 |
| `max_tokens_per_session` | 20K | 50K | 100K |
| `max_cost_per_session` | $0.50 | $1.00 | $5.00 |
| `max_requests_per_minute` | 10 | 20 | 40 |

### `limits/service.py`

**`LimitsService`** — singleton with:

- **Session counters** (`SessionUsage`): tool_calls, turns, tokens_in, tokens_out, estimated_cost
- **Token tracking**: `track_token_usage(session_id, in, out, model)` with per-model pricing
- **Cost estimation**: configurable token pricing (free for local models, market rates for cloud)
- **Rate limiting**: in-memory sliding window per user_id (minute + hour windows)
- **Check methods**: `check_turn_limit`, `check_tool_limits`, `check_token_budget`, `check_rate_limit`
- **Combined entry check**: `check_request_entry` (rate + turns + budget)

---

## 3. Modified Files

### `src/agent/state.py`
- Added 6 new fields: `session_tool_calls`, `session_turns`, `session_tokens_in`, `session_tokens_out`, `session_estimated_cost`, `limit_exceeded`

### `src/agent/nodes/input.py`
- Calls `check_request_entry()` at request entry (rate limit + turn limit + budget)
- Populates session counters in state
- Sets `limit_exceeded` + `final_response` if any limit blocks

### `src/agent/nodes/pre_tool_gate.py`
- Replaced stub `_check_limits()` with real LimitsService integration
- Checks per-request + per-session tool call limits
- Checks token/cost budget before allowing tool calls
- Increments tool call counters on allowed tools

### `src/agent/nodes/llm_call.py`
- Added `_track_tokens()` helper: extracts prompt_tokens/completion_tokens from response, tracks in LimitsService, checks budget post-LLM
- Robust against non-integer values (handles mock objects gracefully)

### `src/agent/graph.py`
- Added `_after_input()` conditional edge: short-circuits to memory when limits exceeded
- Updated `_check_blocked()` to also route to memory on `limit_exceeded`

---

## 4. Check Points

| Point | When | What's checked |
|---|---|---|
| Request entry (`input_node`) | Each user message | Rate limit, turn limit, token budget |
| Pre-tool gate | Before each tool call | Per-request tool count, per-session tool count, token budget |
| Post-LLM call | After response | Token usage accumulated, cost estimated, budget checked |

---

## 5. Test Coverage

**62 new tests** in `tests/test_limits.py`:

| Test Class | Count | Purpose |
|---|---|---|
| `TestLimitsConfig` | 7 | Per-role defaults, frozen config, unknown role fallback |
| `TestSessionUsage` | 6 | Counters, isolation, clearing |
| `TestTokenTracking` | 5 | Tracking, cumulative, cost estimation, free models |
| `TestTurnLimits` | 3 | Under/at/over limit |
| `TestToolCallLimits` | 5 | Per-request, per-session, priority |
| `TestTokenBudget` | 4 | Token budget, cost budget |
| `TestRateLimiting` | 8 | Sliding window, per-minute, per-hour, isolation, clear |
| `TestRequestEntryCheck` | 4 | Combined entry check, turn not incremented on block |
| `TestInputNodeLimits` | 4 | Integration: normal, rate limited, admin higher, counters |
| `TestPreToolGateLimits` | 5 | Tool limits, admin override, token budget, increment |
| `TestGraphLimitRouting` | 5 | Graph routing on limit exceeded |
| `TestEdgeCases` | 6 | Zero tokens, unknown model, independent sessions |

**Total: 354 tests** (292 existing + 62 new), all passing.
