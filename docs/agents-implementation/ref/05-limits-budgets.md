# Guide 5 — Limits & Budgets

**Goal:** Cap tool calls, tokens, cost, and request rate per role and session.
Prevent runaway loops. Kill LLM bill-bombs before they start.

**Time:** 15 minutes

**Depends on:** [Guide 1 — RBAC](01-rbac.md) (uses role to select limits)

---

## Why limits matter

Without limits, one prompt can:

| Attack | Impact |
|--------|--------|
| Infinite loop ("keep searching until you find it") | 100+ tool calls, $$$, DoS |
| Token bomb ("write a 50,000 word essay") | Blow token budget in one turn |
| Session abuse (bot hitting API 1000×/min) | DoS other users |
| Cost bomb ("call GPT-4 for each of 500 items") | $50+ bill from one session |

Limits make all of these impossible.

---

## Step 1: Config per role

```python
# limits_config.py
from dataclasses import dataclass


@dataclass(frozen=True)
class LimitsConfig:
    """Immutable budget caps for one role."""

    # Per request
    max_iterations: int = 5             # LLM→tool loops
    max_tool_calls_per_request: int = 10

    # Per session
    max_tool_calls_per_session: int = 50
    max_turns_per_session: int = 100    # user messages

    # Token / cost
    max_tokens_per_request: int = 8192
    max_tokens_per_session: int = 50_000
    max_cost_per_session: float = 1.00  # USD

    # Rate limits
    max_requests_per_minute: int = 20
    max_requests_per_hour: int = 200


# ── Per-role overrides ────────────────────────────────────

ROLE_LIMITS: dict[str, LimitsConfig] = {
    "customer": LimitsConfig(
        max_iterations=3,
        max_tool_calls_per_request=5,
        max_tool_calls_per_session=20,
        max_turns_per_session=50,
        max_tokens_per_request=4096,
        max_tokens_per_session=20_000,
        max_cost_per_session=0.50,
        max_requests_per_minute=10,
        max_requests_per_hour=100,
    ),
    "support": LimitsConfig(
        max_iterations=5,
        max_tool_calls_per_request=10,
        max_tool_calls_per_session=50,
        max_turns_per_session=100,
        max_tokens_per_request=8192,
        max_tokens_per_session=50_000,
        max_cost_per_session=1.00,
        max_requests_per_minute=20,
        max_requests_per_hour=200,
    ),
    "admin": LimitsConfig(
        max_iterations=10,
        max_tool_calls_per_request=20,
        max_tool_calls_per_session=100,
        max_turns_per_session=200,
        max_tokens_per_request=16_384,
        max_tokens_per_session=100_000,
        max_cost_per_session=5.00,
        max_requests_per_minute=40,
        max_requests_per_hour=400,
    ),
}

DEFAULT_LIMITS = ROLE_LIMITS["customer"]  # Strictest for unknown roles


def get_limits(role: str) -> LimitsConfig:
    return ROLE_LIMITS.get(role, DEFAULT_LIMITS)
```

### Design principle

**Customer** gets the tightest limits. **Admin** gets the most room.
Unknown roles fall back to customer (strictest = safest).

---

## Step 2: Session usage tracker

```python
# limits_service.py
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from limits_config import LimitsConfig, get_limits


@dataclass
class SessionUsage:
    """Mutable counters for one session."""
    tool_calls: int = 0
    turns: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    estimated_cost: float = 0.0


@dataclass(frozen=True)
class LimitCheckResult:
    allowed: bool
    limit_type: str | None = None
    limit_value: int | float | None = None
    current_value: int | float | None = None
    message: str | None = None


LIMIT_OK = LimitCheckResult(allowed=True)

LIMIT_EXCEEDED_MSG = (
    "I've reached the maximum number of operations for this request. "
    "Please try a more specific question or start a new conversation."
)
RATE_LIMIT_MSG = "You're sending requests too quickly. Please wait a moment."


# ── Token pricing (per 1K tokens, USD) ───────────────────

TOKEN_PRICING: dict[str, dict[str, float]] = {
    "default":   {"input": 0.0005, "output": 0.0015},
    "gpt-4o":    {"input": 0.005,  "output": 0.015},
    "llama3:8b": {"input": 0.0,    "output": 0.0},
}


class LimitsService:
    """In-memory limits + rate limiting.

    Good for single-process async (FastAPI/uvicorn).
    For multi-process: swap to Redis-backed counters.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionUsage] = {}
        self._rate_windows: dict[str, list[float]] = defaultdict(list)

    def _get(self, session_id: str) -> SessionUsage:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionUsage()
        return self._sessions[session_id]

    # ── Increment ─────────────────────────────────────────

    def increment_turn(self, session_id: str) -> None:
        self._get(session_id).turns += 1

    def increment_tool_calls(self, session_id: str, count: int = 1) -> None:
        self._get(session_id).tool_calls += count

    def track_tokens(
        self,
        session_id: str,
        tokens_in: int,
        tokens_out: int,
        model: str = "default",
    ) -> None:
        usage = self._get(session_id)
        usage.tokens_in += tokens_in
        usage.tokens_out += tokens_out
        pricing = TOKEN_PRICING.get(model, TOKEN_PRICING["default"])
        usage.estimated_cost += (
            tokens_in / 1000 * pricing["input"]
            + tokens_out / 1000 * pricing["output"]
        )

    # ── Checks ────────────────────────────────────────────

    def check_turn_limit(
        self, session_id: str, config: LimitsConfig
    ) -> LimitCheckResult:
        usage = self._get(session_id)
        if usage.turns >= config.max_turns_per_session:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_turns_per_session",
                limit_value=config.max_turns_per_session,
                current_value=usage.turns,
                message=LIMIT_EXCEEDED_MSG,
            )
        return LIMIT_OK

    def check_tool_limits(
        self,
        session_id: str,
        config: LimitsConfig,
        request_tool_calls: int = 0,
    ) -> LimitCheckResult:
        usage = self._get(session_id)

        # Per-request
        if request_tool_calls >= config.max_tool_calls_per_request:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_tool_calls_per_request",
                limit_value=config.max_tool_calls_per_request,
                current_value=request_tool_calls,
                message=LIMIT_EXCEEDED_MSG,
            )

        # Per-session
        if usage.tool_calls >= config.max_tool_calls_per_session:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_tool_calls_per_session",
                limit_value=config.max_tool_calls_per_session,
                current_value=usage.tool_calls,
                message=LIMIT_EXCEEDED_MSG,
            )

        return LIMIT_OK

    def check_token_budget(
        self, session_id: str, config: LimitsConfig
    ) -> LimitCheckResult:
        usage = self._get(session_id)
        total = usage.tokens_in + usage.tokens_out

        if total >= config.max_tokens_per_session:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_tokens_per_session",
                limit_value=config.max_tokens_per_session,
                current_value=total,
                message=LIMIT_EXCEEDED_MSG,
            )
        if usage.estimated_cost >= config.max_cost_per_session:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_cost_per_session",
                limit_value=config.max_cost_per_session,
                current_value=usage.estimated_cost,
                message=LIMIT_EXCEEDED_MSG,
            )
        return LIMIT_OK

    def check_rate_limit(
        self, user_id: str, config: LimitsConfig
    ) -> LimitCheckResult:
        now = time.time()

        # Prune > 1 hour old
        cutoff = now - 3600
        self._rate_windows[user_id] = [
            ts for ts in self._rate_windows[user_id] if ts > cutoff
        ]
        timestamps = self._rate_windows[user_id]

        # Per-minute
        minute_count = sum(1 for ts in timestamps if ts > now - 60)
        if minute_count >= config.max_requests_per_minute:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_requests_per_minute",
                limit_value=config.max_requests_per_minute,
                current_value=minute_count,
                message=RATE_LIMIT_MSG,
            )

        # Per-hour
        if len(timestamps) >= config.max_requests_per_hour:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_requests_per_hour",
                limit_value=config.max_requests_per_hour,
                current_value=len(timestamps),
                message=RATE_LIMIT_MSG,
            )

        timestamps.append(now)
        return LIMIT_OK

    # ── Convenience: run all entry-point checks ──────────

    def check_request_entry(
        self,
        session_id: str,
        user_id: str,
        role: str,
    ) -> LimitCheckResult:
        """Run all checks at request entry (input node).

        Order: rate limit → turn limit → token/cost budget.
        On success, increments turn counter.
        """
        config = get_limits(role)

        for check in [
            lambda: self.check_rate_limit(user_id, config),
            lambda: self.check_turn_limit(session_id, config),
            lambda: self.check_token_budget(session_id, config),
        ]:
            result = check()
            if not result.allowed:
                return result

        self.increment_turn(session_id)
        return LIMIT_OK

    def get_usage(self, session_id: str) -> dict[str, Any]:
        """Return current counters (for logging/observability)."""
        u = self._get(session_id)
        return {
            "tool_calls": u.tool_calls,
            "turns": u.turns,
            "tokens_in": u.tokens_in,
            "tokens_out": u.tokens_out,
            "estimated_cost": round(u.estimated_cost, 6),
        }
```

---

## Step 3: Wiring

### Where to check limits

| Checkpoint | What to check | When |
|-----------|--------------|------|
| **Request entry** | rate limit + turn limit + budget | Before any processing |
| **Pre-tool gate** | tool call count (per-request + session) | Before each tool call |
| **Post-LLM** | token usage tracking | After each LLM response |
| **Loop guard** | iteration count | Each LLM→tool cycle |

### Option A — Raw Python

```python
limits = LimitsService()

def handle_request(session_id: str, user_id: str, role: str, message: str):
    # 1. Entry check
    entry_check = limits.check_request_entry(session_id, user_id, role)
    if not entry_check.allowed:
        return {"error": entry_check.message}

    config = get_limits(role)
    iteration = 0

    while True:
        iteration += 1
        # 2. Loop guard
        if iteration > config.max_iterations:
            return {"error": LIMIT_EXCEEDED_MSG}

        # ... call LLM ...
        llm_response = call_llm(message)

        # 3. Track tokens
        limits.track_tokens(session_id, llm_response.tokens_in, llm_response.tokens_out)

        if not llm_response.has_tool_call:
            return {"response": llm_response.text}

        # 4. Pre-tool: check tool limits
        tool_check = limits.check_tool_limits(
            session_id, config, request_tool_calls=iteration
        )
        if not tool_check.allowed:
            return {"error": tool_check.message}

        # Execute tool
        result = execute_tool(llm_response.tool_call)
        limits.increment_tool_calls(session_id)
        message = result  # feed back to LLM
```

### Option B — LangGraph node

```python
from langgraph.graph import StateGraph

def check_limits_node(state):
    limits = get_limits_service()
    config = get_limits(state["role"])

    result = limits.check_tool_limits(
        state["session_id"],
        config,
        request_tool_calls=state.get("tool_call_count", 0),
    )

    if not result.allowed:
        return {
            "gate_decision": "BLOCK",
            "gate_message": result.message,
        }

    return {"gate_decision": "ALLOW"}


graph = StateGraph(AgentState)
# ... add nodes ...
graph.add_edge("pre_tool_gate", "check_limits")
graph.add_edge("check_limits", "execute_tool")
```

### Option C — Decorator

```python
def enforce_limits(session_id: str, user_id: str, role: str):
    """Decorator that checks rate + turn + budget limits."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            result = limits.check_request_entry(session_id, user_id, role)
            if not result.allowed:
                raise LimitExceededError(result.message)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
```

---

## Config checklist

- [ ] Customer limits are the **strictest** (safest default)
- [ ] Unknown roles fall back to customer
- [ ] `max_iterations` prevents infinite loops (3-10)
- [ ] `max_cost_per_session` prevents bill-bombs
- [ ] Rate limits prevent DoS from single user
- [ ] Token pricing matches your actual provider costs
- [ ] Limits are immutable (`frozen=True`) — code can't change them at runtime

---

## Testing

```python
from limits_config import get_limits
from limits_service import LimitsService

limits = LimitsService()

# Turn limit
config = get_limits("customer")  # max_turns_per_session=50
for i in range(50):
    limits.increment_turn("sess-1")
result = limits.check_turn_limit("sess-1", config)
assert not result.allowed
assert result.limit_type == "max_turns_per_session"

# Tool call limit
config = get_limits("customer")  # max_tool_calls_per_request=5
result = limits.check_tool_limits("sess-2", config, request_tool_calls=5)
assert not result.allowed
assert result.limit_type == "max_tool_calls_per_request"

# Token budget
config = get_limits("customer")  # max_tokens_per_session=20_000
limits.track_tokens("sess-3", tokens_in=15_000, tokens_out=6_000)
result = limits.check_token_budget("sess-3", config)
assert not result.allowed
assert result.limit_type == "max_tokens_per_session"

# Rate limit
config = get_limits("customer")  # max_requests_per_minute=10
for i in range(10):
    limits.check_rate_limit("user-1", config)
result = limits.check_rate_limit("user-1", config)
assert not result.allowed
assert result.limit_type == "max_requests_per_minute"

# Unknown role → customer limits (strictest)
config = get_limits("hacker")
assert config.max_iterations == 3
assert config.max_cost_per_session == 0.50

print("✅ All limits tests passed")
```

---

## Next step

Budgets are enforced.
Next: [Guide 6 — Confirmation Flows](06-confirmation-flows.md) — require human approval for dangerous tools before execution.
