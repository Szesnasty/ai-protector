"""Limits service — session counters, rate limiting, budget tracking.

Spec: docs/agents/06-agents-limits-budgets/SPEC.md

Singleton service that tracks:
  - Per-session: tool calls, turns, tokens (in/out), estimated cost
  - Per-user: sliding window rate limits (in-memory, no Redis needed)
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import structlog

from src.agent.limits.config import LimitsConfig, get_limits_for_role

logger = structlog.get_logger()

# ── Approximate token pricing (per 1K tokens, USD) ───────────────────
# Defaults for local models; overridden per model if needed.

TOKEN_PRICING: dict[str, dict[str, float]] = {
    "default": {"input": 0.0005, "output": 0.0015},
    "llama3.1:8b": {"input": 0.0, "output": 0.0},  # Local model, free
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5": {"input": 0.0008, "output": 0.004},
    "claude-opus-4-6": {"input": 0.015, "output": 0.075},
}

# ── Safe completion message ──────────────────────────────────────────

LIMIT_EXCEEDED_MESSAGE = (
    "I've reached the maximum number of operations for this request. "
    "Please try a more specific question or start a new conversation."
)

RATE_LIMIT_MESSAGE = "You're sending requests too quickly. Please wait a moment and try again."


# ── Session usage tracker ────────────────────────────────────────────


@dataclass
class SessionUsage:
    """Mutable counters for a single session."""

    tool_calls: int = 0
    turns: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    estimated_cost: float = 0.0


# ── Check result ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class LimitCheckResult:
    """Outcome of a limit check."""

    allowed: bool
    limit_type: str | None = None  # Which limit was hit
    limit_value: int | float | None = None
    current_value: int | float | None = None
    message: str | None = None  # User-facing error message


LIMIT_OK = LimitCheckResult(allowed=True)


# ── Service ──────────────────────────────────────────────────────────


class LimitsService:
    """In-memory limits + rate limit service.

    Thread-safety: acceptable for single-process async (FastAPI + uvicorn).
    For multi-process, replace with Redis-backed counters.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionUsage] = {}
        # Rate limit: user_id → list of timestamps
        self._rate_windows: dict[str, list[float]] = defaultdict(list)

    # ── Session usage ─────────────────────────────────────────────

    def get_or_create_session(self, session_id: str) -> SessionUsage:
        """Get or initialise counters for a session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionUsage()
        return self._sessions[session_id]

    def get_session_usage(self, session_id: str) -> dict[str, Any]:
        """Return current session counters as a dict (for state/observability)."""
        usage = self.get_or_create_session(session_id)
        return {
            "session_tool_calls": usage.tool_calls,
            "session_turns": usage.turns,
            "session_tokens_in": usage.tokens_in,
            "session_tokens_out": usage.tokens_out,
            "session_estimated_cost": usage.estimated_cost,
        }

    def increment_turn(self, session_id: str) -> None:
        """Increment the turn counter for a session (called on each user message)."""
        usage = self.get_or_create_session(session_id)
        usage.turns += 1

    def increment_tool_calls(self, session_id: str, count: int = 1) -> None:
        """Increment tool call counter."""
        usage = self.get_or_create_session(session_id)
        usage.tool_calls += count

    def track_token_usage(
        self,
        session_id: str,
        tokens_in: int,
        tokens_out: int,
        model: str = "default",
    ) -> dict[str, Any]:
        """Track token usage and estimate cost. Returns updated counters."""
        usage = self.get_or_create_session(session_id)
        usage.tokens_in += tokens_in
        usage.tokens_out += tokens_out

        # Cost estimation
        pricing = TOKEN_PRICING.get(model, TOKEN_PRICING["default"])
        cost = (tokens_in / 1000 * pricing["input"]) + (tokens_out / 1000 * pricing["output"])
        usage.estimated_cost += cost

        logger.info(
            "token_usage_tracked",
            session_id=session_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_delta=round(cost, 6),
            total_tokens_in=usage.tokens_in,
            total_tokens_out=usage.tokens_out,
            total_cost=round(usage.estimated_cost, 6),
        )

        return {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_delta": cost,
            "session_tokens_in": usage.tokens_in,
            "session_tokens_out": usage.tokens_out,
            "session_estimated_cost": usage.estimated_cost,
        }

    def clear_session(self, session_id: str) -> None:
        """Remove session counters."""
        self._sessions.pop(session_id, None)

    # ── Limit checks ─────────────────────────────────────────────

    def check_turn_limit(self, session_id: str, config: LimitsConfig) -> LimitCheckResult:
        """Check if session has exceeded max turns."""
        usage = self.get_or_create_session(session_id)
        if usage.turns >= config.max_turns_per_session:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_turns_per_session",
                limit_value=config.max_turns_per_session,
                current_value=usage.turns,
                message=LIMIT_EXCEEDED_MESSAGE,
            )
        return LIMIT_OK

    def check_tool_limits(
        self,
        session_id: str,
        config: LimitsConfig,
        request_tool_calls: int = 0,
    ) -> LimitCheckResult:
        """Check per-request and per-session tool call limits.

        Args:
            session_id: Session identifier.
            config: Limits config for the user's role.
            request_tool_calls: Number of tool calls already made in current request.
        """
        usage = self.get_or_create_session(session_id)

        # Per-request limit
        if request_tool_calls >= config.max_tool_calls_per_request:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_tool_calls_per_request",
                limit_value=config.max_tool_calls_per_request,
                current_value=request_tool_calls,
                message=LIMIT_EXCEEDED_MESSAGE,
            )

        # Per-session limit
        if usage.tool_calls >= config.max_tool_calls_per_session:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_tool_calls_per_session",
                limit_value=config.max_tool_calls_per_session,
                current_value=usage.tool_calls,
                message=LIMIT_EXCEEDED_MESSAGE,
            )

        return LIMIT_OK

    def check_token_budget(self, session_id: str, config: LimitsConfig) -> LimitCheckResult:
        """Check if session has exceeded token or cost budgets."""
        usage = self.get_or_create_session(session_id)

        # Token budget
        total_tokens = usage.tokens_in + usage.tokens_out
        if total_tokens >= config.max_tokens_per_session:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_tokens_per_session",
                limit_value=config.max_tokens_per_session,
                current_value=total_tokens,
                message=LIMIT_EXCEEDED_MESSAGE,
            )

        # Cost budget
        if usage.estimated_cost >= config.max_cost_per_session:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_cost_per_session",
                limit_value=config.max_cost_per_session,
                current_value=usage.estimated_cost,
                message=LIMIT_EXCEEDED_MESSAGE,
            )

        return LIMIT_OK

    # ── Rate limiting (in-memory sliding window) ─────────────────

    def check_rate_limit(self, user_id: str, config: LimitsConfig) -> LimitCheckResult:
        """Check per-user rate limits using in-memory sliding window.

        Checks both per-minute and per-hour windows.
        """
        now = time.time()
        timestamps = self._rate_windows[user_id]

        # Prune timestamps older than 1 hour
        cutoff_hour = now - 3600
        self._rate_windows[user_id] = [ts for ts in timestamps if ts > cutoff_hour]
        timestamps = self._rate_windows[user_id]

        # Per-minute check
        cutoff_minute = now - 60
        requests_in_minute = sum(1 for ts in timestamps if ts > cutoff_minute)
        if requests_in_minute >= config.max_requests_per_minute:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_requests_per_minute",
                limit_value=config.max_requests_per_minute,
                current_value=requests_in_minute,
                message=RATE_LIMIT_MESSAGE,
            )

        # Per-hour check
        requests_in_hour = len(timestamps)
        if requests_in_hour >= config.max_requests_per_hour:
            return LimitCheckResult(
                allowed=False,
                limit_type="max_requests_per_hour",
                limit_value=config.max_requests_per_hour,
                current_value=requests_in_hour,
                message=RATE_LIMIT_MESSAGE,
            )

        # Record this request
        timestamps.append(now)

        return LIMIT_OK

    def clear_rate_limits(self, user_id: str) -> None:
        """Clear rate limit history for a user (for testing)."""
        self._rate_windows.pop(user_id, None)

    # ── Combined check (convenience) ─────────────────────────────

    def check_request_entry(
        self,
        session_id: str,
        user_id: str,
        role: str,
    ) -> LimitCheckResult:
        """Run all entry-point limit checks (called from input_node).

        Checks: rate limit, turn limit
        Increments: turn counter
        """
        config = get_limits_for_role(role)

        # Rate limit
        rate_result = self.check_rate_limit(user_id, config)
        if not rate_result.allowed:
            self._log_limit_exceeded(rate_result, session_id, role)
            return rate_result

        # Turn limit
        turn_result = self.check_turn_limit(session_id, config)
        if not turn_result.allowed:
            self._log_limit_exceeded(turn_result, session_id, role)
            return turn_result

        # Token / cost budget (prevent starting new requests on exhausted sessions)
        budget_result = self.check_token_budget(session_id, config)
        if not budget_result.allowed:
            self._log_limit_exceeded(budget_result, session_id, role)
            return budget_result

        # All OK — increment turn
        self.increment_turn(session_id)
        return LIMIT_OK

    def _log_limit_exceeded(self, result: LimitCheckResult, session_id: str, role: str) -> None:
        """Log a limit exceeded event."""
        logger.warning(
            "limit_exceeded",
            limit_type=result.limit_type,
            limit_value=result.limit_value,
            current_value=result.current_value,
            session_id=session_id,
            user_role=role,
        )


# ── Module-level singleton ────────────────────────────────────────────

_service: LimitsService | None = None


def get_limits_service() -> LimitsService:
    """Get or create the singleton LimitsService."""
    global _service
    if _service is None:
        _service = LimitsService()
    return _service
