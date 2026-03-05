"""Limits configuration — per-role caps for iterations, tools, tokens, cost, rate.

Spec: docs/agents/06-agents-limits-budgets/SPEC.md
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LimitsConfig:
    """Immutable configuration for a single role's limits."""

    # ── Per-request ────────────────────────────────────────
    max_iterations: int = 5
    max_tool_calls_per_request: int = 10

    # ── Per-session ────────────────────────────────────────
    max_tool_calls_per_session: int = 50
    max_turns_per_session: int = 100

    # ── Token / cost budgets ───────────────────────────────
    max_tokens_per_request: int = 8192
    max_tokens_per_session: int = 50_000
    max_cost_per_session: float = 1.00  # USD

    # ── Rate limits ────────────────────────────────────────
    max_requests_per_minute: int = 20
    max_requests_per_hour: int = 200


# ── Per-role default overrides ────────────────────────────────────────

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

# Fallback for unknown roles
DEFAULT_LIMITS = ROLE_LIMITS["customer"]


def get_limits_for_role(role: str) -> LimitsConfig:
    """Return the LimitsConfig for a given role, falling back to DEFAULT."""
    return ROLE_LIMITS.get(role, DEFAULT_LIMITS)
