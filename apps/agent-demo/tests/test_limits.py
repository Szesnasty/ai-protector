"""Tests for limits, rate limiting, iteration caps, budget caps (spec 06).

Covers:
  - LimitsConfig: per-role defaults
  - LimitsService: session counters, token tracking, cost estimation
  - Rate limiting: sliding window
  - Tool call limits: per-request and per-session
  - Turn limits
  - Token/cost budget enforcement
  - Integration with input_node and pre_tool_gate
"""

from __future__ import annotations

import time

import pytest

from src.agent.limits.config import (
    DEFAULT_LIMITS,
    ROLE_LIMITS,
    LimitsConfig,
    get_limits_for_role,
)
from src.agent.limits.service import (
    LIMIT_EXCEEDED_MESSAGE,
    LIMIT_OK,
    RATE_LIMIT_MESSAGE,
    LimitsService,
    get_limits_service,
)

# ══════════════════════════════════════════════════════════════════════
# LimitsConfig
# ══════════════════════════════════════════════════════════════════════


class TestLimitsConfig:
    """Test limits configuration and per-role defaults."""

    def test_default_limits_match_customer(self):
        assert ROLE_LIMITS["customer"] == DEFAULT_LIMITS

    def test_customer_limits(self):
        cfg = get_limits_for_role("customer")
        assert cfg.max_iterations == 3
        assert cfg.max_tool_calls_per_request == 5
        assert cfg.max_tool_calls_per_session == 20
        assert cfg.max_turns_per_session == 50
        assert cfg.max_tokens_per_session == 20_000
        assert cfg.max_cost_per_session == 0.50

    def test_support_limits(self):
        cfg = get_limits_for_role("support")
        assert cfg.max_iterations == 5
        assert cfg.max_tool_calls_per_session == 50
        assert cfg.max_tokens_per_session == 50_000

    def test_admin_limits_higher(self):
        cfg = get_limits_for_role("admin")
        assert cfg.max_iterations == 10
        assert cfg.max_tool_calls_per_session == 100
        assert cfg.max_tokens_per_session == 100_000
        assert cfg.max_cost_per_session == 5.00

    def test_unknown_role_gets_default(self):
        cfg = get_limits_for_role("unknown")
        assert cfg == DEFAULT_LIMITS

    def test_admin_limits_greater_than_customer(self):
        admin = get_limits_for_role("admin")
        customer = get_limits_for_role("customer")
        assert admin.max_tool_calls_per_session > customer.max_tool_calls_per_session
        assert admin.max_tokens_per_session > customer.max_tokens_per_session
        assert admin.max_cost_per_session > customer.max_cost_per_session

    def test_config_is_frozen(self):
        cfg = get_limits_for_role("customer")
        with pytest.raises(AttributeError):
            cfg.max_iterations = 99  # type: ignore


# ══════════════════════════════════════════════════════════════════════
# LimitsService — Session Usage
# ══════════════════════════════════════════════════════════════════════


class TestSessionUsage:
    """Test session counter management."""

    def setup_method(self):
        self.svc = LimitsService()

    def test_new_session_has_zero_counters(self):
        usage = self.svc.get_session_usage("s1")
        assert usage["session_tool_calls"] == 0
        assert usage["session_turns"] == 0
        assert usage["session_tokens_in"] == 0
        assert usage["session_tokens_out"] == 0
        assert usage["session_estimated_cost"] == 0.0

    def test_increment_turn(self):
        self.svc.increment_turn("s1")
        self.svc.increment_turn("s1")
        usage = self.svc.get_session_usage("s1")
        assert usage["session_turns"] == 2

    def test_increment_tool_calls(self):
        self.svc.increment_tool_calls("s1", 3)
        usage = self.svc.get_session_usage("s1")
        assert usage["session_tool_calls"] == 3

    def test_increment_tool_calls_default_one(self):
        self.svc.increment_tool_calls("s1")
        assert self.svc.get_session_usage("s1")["session_tool_calls"] == 1

    def test_clear_session(self):
        self.svc.increment_turn("s1")
        self.svc.clear_session("s1")
        # After clear, a fresh session is created
        usage = self.svc.get_session_usage("s1")
        assert usage["session_turns"] == 0

    def test_sessions_isolated(self):
        self.svc.increment_turn("s1")
        self.svc.increment_tool_calls("s2", 5)
        assert self.svc.get_session_usage("s1")["session_turns"] == 1
        assert self.svc.get_session_usage("s1")["session_tool_calls"] == 0
        assert self.svc.get_session_usage("s2")["session_tool_calls"] == 5
        assert self.svc.get_session_usage("s2")["session_turns"] == 0


# ══════════════════════════════════════════════════════════════════════
# LimitsService — Token Tracking & Cost
# ══════════════════════════════════════════════════════════════════════


class TestTokenTracking:
    """Test token usage tracking and cost estimation."""

    def setup_method(self):
        self.svc = LimitsService()

    def test_track_tokens(self):
        result = self.svc.track_token_usage("s1", 100, 50, "default")
        assert result["tokens_in"] == 100
        assert result["tokens_out"] == 50
        assert result["session_tokens_in"] == 100
        assert result["session_tokens_out"] == 50

    def test_cumulative_tracking(self):
        self.svc.track_token_usage("s1", 100, 50)
        result = self.svc.track_token_usage("s1", 200, 100)
        assert result["session_tokens_in"] == 300
        assert result["session_tokens_out"] == 150

    def test_cost_estimation_default(self):
        # default pricing: input $0.0005/1K, output $0.0015/1K
        result = self.svc.track_token_usage("s1", 1000, 1000, "default")
        expected_cost = (1000 / 1000 * 0.0005) + (1000 / 1000 * 0.0015)
        assert abs(result["cost_delta"] - expected_cost) < 1e-8

    def test_cost_estimation_local_model_free(self):
        result = self.svc.track_token_usage("s1", 1000, 1000, "llama3.1:8b")
        assert result["cost_delta"] == 0.0

    def test_cost_estimation_cumulative(self):
        self.svc.track_token_usage("s1", 1000, 1000, "default")
        result = self.svc.track_token_usage("s1", 1000, 1000, "default")
        expected_single = (1000 / 1000 * 0.0005) + (1000 / 1000 * 0.0015)
        assert abs(result["session_estimated_cost"] - expected_single * 2) < 1e-8


# ══════════════════════════════════════════════════════════════════════
# LimitsService — Turn Limits
# ══════════════════════════════════════════════════════════════════════


class TestTurnLimits:
    """Test session turn limit enforcement."""

    def setup_method(self):
        self.svc = LimitsService()
        self.config = LimitsConfig(max_turns_per_session=3)

    def test_under_limit_allowed(self):
        self.svc.increment_turn("s1")
        result = self.svc.check_turn_limit("s1", self.config)
        assert result.allowed is True

    def test_at_limit_blocked(self):
        for _ in range(3):
            self.svc.increment_turn("s1")
        result = self.svc.check_turn_limit("s1", self.config)
        assert result.allowed is False
        assert result.limit_type == "max_turns_per_session"
        assert result.limit_value == 3
        assert result.current_value == 3

    def test_over_limit_blocked(self):
        for _ in range(5):
            self.svc.increment_turn("s1")
        result = self.svc.check_turn_limit("s1", self.config)
        assert result.allowed is False


# ══════════════════════════════════════════════════════════════════════
# LimitsService — Tool Call Limits
# ══════════════════════════════════════════════════════════════════════


class TestToolCallLimits:
    """Test per-request and per-session tool call limits."""

    def setup_method(self):
        self.svc = LimitsService()
        self.config = LimitsConfig(
            max_tool_calls_per_request=3,
            max_tool_calls_per_session=10,
        )

    def test_under_request_limit(self):
        result = self.svc.check_tool_limits("s1", self.config, request_tool_calls=2)
        assert result.allowed is True

    def test_at_request_limit_blocked(self):
        result = self.svc.check_tool_limits("s1", self.config, request_tool_calls=3)
        assert result.allowed is False
        assert result.limit_type == "max_tool_calls_per_request"

    def test_under_session_limit(self):
        self.svc.increment_tool_calls("s1", 9)
        result = self.svc.check_tool_limits("s1", self.config, request_tool_calls=0)
        assert result.allowed is True

    def test_at_session_limit_blocked(self):
        self.svc.increment_tool_calls("s1", 10)
        result = self.svc.check_tool_limits("s1", self.config, request_tool_calls=0)
        assert result.allowed is False
        assert result.limit_type == "max_tool_calls_per_session"
        assert result.current_value == 10

    def test_request_limit_checked_first(self):
        """Per-request limit is checked before per-session limit."""
        self.svc.increment_tool_calls("s1", 10)
        result = self.svc.check_tool_limits("s1", self.config, request_tool_calls=5)
        # Both limits exceeded, but request limit checked first
        assert result.limit_type == "max_tool_calls_per_request"


# ══════════════════════════════════════════════════════════════════════
# LimitsService — Token / Cost Budget
# ══════════════════════════════════════════════════════════════════════


class TestTokenBudget:
    """Test token and cost budget enforcement."""

    def setup_method(self):
        self.svc = LimitsService()

    def test_under_token_budget(self):
        config = LimitsConfig(max_tokens_per_session=1000)
        self.svc.track_token_usage("s1", 400, 100)
        result = self.svc.check_token_budget("s1", config)
        assert result.allowed is True

    def test_at_token_budget_blocked(self):
        config = LimitsConfig(max_tokens_per_session=1000)
        self.svc.track_token_usage("s1", 800, 200)
        result = self.svc.check_token_budget("s1", config)
        assert result.allowed is False
        assert result.limit_type == "max_tokens_per_session"

    def test_under_cost_budget(self):
        config = LimitsConfig(max_cost_per_session=1.00)
        # default: $0.0005/1K in + $0.0015/1K out = $0.002 total
        self.svc.track_token_usage("s1", 1000, 1000, "default")
        result = self.svc.check_token_budget("s1", config)
        assert result.allowed is True

    def test_cost_budget_exceeded(self):
        config = LimitsConfig(max_cost_per_session=0.001, max_tokens_per_session=999_999)
        # default pricing: 10K tokens = ~$0.02
        self.svc.track_token_usage("s1", 10_000, 10_000, "default")
        result = self.svc.check_token_budget("s1", config)
        assert result.allowed is False
        assert result.limit_type == "max_cost_per_session"


# ══════════════════════════════════════════════════════════════════════
# LimitsService — Rate Limiting
# ══════════════════════════════════════════════════════════════════════


class TestRateLimiting:
    """Test in-memory sliding window rate limits."""

    def setup_method(self):
        self.svc = LimitsService()
        self.config = LimitsConfig(
            max_requests_per_minute=3,
            max_requests_per_hour=10,
        )

    def test_first_request_allowed(self):
        result = self.svc.check_rate_limit("u1", self.config)
        assert result.allowed is True

    def test_within_per_minute_limit(self):
        self.svc.check_rate_limit("u1", self.config)
        self.svc.check_rate_limit("u1", self.config)
        result = self.svc.check_rate_limit("u1", self.config)
        assert result.allowed is True  # 3rd request, at limit

    def test_exceeds_per_minute_limit(self):
        for _ in range(3):
            self.svc.check_rate_limit("u1", self.config)
        result = self.svc.check_rate_limit("u1", self.config)
        assert result.allowed is False
        assert result.limit_type == "max_requests_per_minute"

    def test_per_minute_window_slides(self):
        """After a minute, old requests fall out of window."""
        past = time.time() - 61  # 61 seconds ago
        self.svc._rate_windows["u1"] = [past, past, past]
        result = self.svc.check_rate_limit("u1", self.config)
        assert result.allowed is True  # old timestamps pruned

    def test_per_hour_limit(self):
        config = LimitsConfig(max_requests_per_minute=100, max_requests_per_hour=5)
        for _ in range(5):
            self.svc.check_rate_limit("u1", config)
        result = self.svc.check_rate_limit("u1", config)
        assert result.allowed is False
        assert result.limit_type == "max_requests_per_hour"

    def test_users_isolated(self):
        for _ in range(3):
            self.svc.check_rate_limit("u1", self.config)
        # u1 is at limit, but u2 should be fine
        result = self.svc.check_rate_limit("u2", self.config)
        assert result.allowed is True

    def test_clear_rate_limits(self):
        for _ in range(3):
            self.svc.check_rate_limit("u1", self.config)
        self.svc.clear_rate_limits("u1")
        result = self.svc.check_rate_limit("u1", self.config)
        assert result.allowed is True

    def test_rate_limit_message(self):
        for _ in range(3):
            self.svc.check_rate_limit("u1", self.config)
        result = self.svc.check_rate_limit("u1", self.config)
        assert result.message == RATE_LIMIT_MESSAGE


# ══════════════════════════════════════════════════════════════════════
# LimitsService — Combined Entry Check
# ══════════════════════════════════════════════════════════════════════


class TestRequestEntryCheck:
    """Test check_request_entry (combined check called from input_node)."""

    def setup_method(self):
        self.svc = LimitsService()

    def test_normal_request_allowed(self):
        result = self.svc.check_request_entry("s1", "u1", "customer")
        assert result.allowed is True
        # Turn should be incremented
        usage = self.svc.get_session_usage("s1")
        assert usage["session_turns"] == 1

    def test_turn_not_incremented_on_limit(self):
        """When rate limit blocks, turn should NOT be incremented."""
        # Exhaust per-minute rate limit for customer (10/min)
        for i in range(10):
            self.svc.check_request_entry(f"s{i}", "u1", "customer")
        result = self.svc.check_request_entry("s_new", "u1", "customer")
        assert result.allowed is False
        assert result.limit_type == "max_requests_per_minute"
        # The new session should have 0 turns (rate limit blocked before increment)
        usage = self.svc.get_session_usage("s_new")
        assert usage["session_turns"] == 0

    def test_turn_limit_blocks(self):
        # Customer has max 50 turns. Use a custom config by exhausting turns.
        config = LimitsConfig(max_turns_per_session=2, max_requests_per_minute=100, max_requests_per_hour=1000)
        # Manually set turns
        session = self.svc.get_or_create_session("s1")
        session.turns = 2
        result = self.svc.check_turn_limit("s1", config)
        assert result.allowed is False

    def test_token_budget_blocks_at_entry(self):
        """If session already exhausted token budget, new requests are blocked."""
        # Exhaust token budget
        self.svc.track_token_usage("s1", 20_000, 5_000, "default")
        # Customer has max 20K tokens per session
        result = self.svc.check_request_entry("s1", "u1", "customer")
        assert result.allowed is False
        assert result.limit_type == "max_tokens_per_session"


# ══════════════════════════════════════════════════════════════════════
# Integration — Input Node
# ══════════════════════════════════════════════════════════════════════


class TestInputNodeLimits:
    """Test that input_node enforces limits at request entry."""

    def setup_method(self):
        # Reset limits service singleton
        import src.agent.limits.service as svc_mod

        svc_mod._service = LimitsService()
        self.svc = svc_mod._service

    def test_normal_request_passes(self):
        from src.agent.nodes.input import input_node
        from src.session import session_store

        session_store._sessions.clear()
        state = {
            "session_id": "test-limits-ok",
            "message": "hello",
            "user_role": "customer",
        }
        result = input_node(state)
        assert result.get("limit_exceeded") is None
        assert "final_response" not in result or result.get("final_response") is None

    def test_rate_limited_request_blocked(self):
        from src.agent.nodes.input import input_node
        from src.session import session_store

        session_store._sessions.clear()
        # Exhaust per-minute rate limit for customer (10/min)
        # input_node uses session_id as user_id, so use same session_id
        for i in range(10):
            input_node(
                {
                    "session_id": "rl-same",
                    "message": "hi",
                    "user_role": "customer",
                }
            )

        result = input_node(
            {
                "session_id": "rl-same",
                "message": "hi again",
                "user_role": "customer",
            }
        )
        assert result["limit_exceeded"] == "max_requests_per_minute"
        assert result["final_response"] == RATE_LIMIT_MESSAGE

    def test_admin_higher_rate_limit(self):
        from src.agent.nodes.input import input_node
        from src.session import session_store

        session_store._sessions.clear()
        # Admin has 40/min, send 11 requests (customer limit is 10)
        # Use same session_id so rate limiter sees same user
        for i in range(11):
            result = input_node(
                {
                    "session_id": "admin-rl",
                    "message": "check",
                    "user_role": "admin",
                }
            )
        # 11th request should still pass for admin
        assert result.get("limit_exceeded") is None

    def test_session_counters_in_state(self):
        from src.agent.nodes.input import input_node
        from src.session import session_store

        session_store._sessions.clear()
        state = {
            "session_id": "test-counters",
            "message": "hello",
            "user_role": "customer",
        }
        result = input_node(state)
        assert "session_tool_calls" in result
        assert "session_turns" in result
        assert "session_tokens_in" in result
        assert "session_tokens_out" in result
        assert "session_estimated_cost" in result
        assert result["session_turns"] == 1


# ══════════════════════════════════════════════════════════════════════
# Integration — Pre-Tool Gate Limits
# ══════════════════════════════════════════════════════════════════════


class TestPreToolGateLimits:
    """Test that pre_tool_gate enforces tool call limits."""

    def setup_method(self):
        import src.agent.limits.service as svc_mod

        svc_mod._service = LimitsService()
        self.svc = svc_mod._service

    def test_tool_calls_within_limit(self):
        from src.agent.nodes.pre_tool_gate import pre_tool_gate_node

        state = {
            "session_id": "gate-ok",
            "user_role": "customer",
            "message": "check order",
            "chat_history": [],
            "allowed_tools": ["getOrderStatus"],
            "tool_plan": [{"tool": "getOrderStatus", "args": {"order_id": "ORD-001"}}],
            "tool_calls": [],
            "iterations": 0,
        }
        result = pre_tool_gate_node(state)
        # Tool should be allowed
        assert len(result["tool_plan"]) == 1
        decisions = result["gate_decisions"]
        assert decisions[0]["decision"] in ("ALLOW", "MODIFY")

    def test_session_tool_limit_blocks(self):
        from src.agent.nodes.pre_tool_gate import pre_tool_gate_node

        # Exhaust session tool limit (customer: 20)
        self.svc.increment_tool_calls("gate-limit", 20)

        state = {
            "session_id": "gate-limit",
            "user_role": "customer",
            "message": "check order",
            "chat_history": [],
            "allowed_tools": ["getOrderStatus"],
            "tool_plan": [{"tool": "getOrderStatus", "args": {"order_id": "ORD-001"}}],
            "tool_calls": [],
            "iterations": 0,
        }
        result = pre_tool_gate_node(state)
        # Tool should be blocked
        decisions = result["gate_decisions"]
        assert decisions[0]["decision"] == "BLOCK"
        assert "max_tool_calls_per_session" in decisions[0]["reason"]

    def test_admin_higher_tool_limit(self):
        from src.agent.nodes.pre_tool_gate import pre_tool_gate_node

        # Admin can do 100 tool calls; 20 is fine
        self.svc.increment_tool_calls("gate-admin", 20)

        state = {
            "session_id": "gate-admin",
            "user_role": "admin",
            "message": "check",
            "chat_history": [],
            "allowed_tools": ["getOrderStatus"],
            "tool_plan": [{"tool": "getOrderStatus", "args": {"order_id": "ORD-001"}}],
            "tool_calls": [],
            "iterations": 0,
        }
        result = pre_tool_gate_node(state)
        decisions = result["gate_decisions"]
        # Should pass since admin has higher limits
        limits_checks = [c for d in decisions for c in d["checks"] if c["check"] == "limits"]
        assert all(c["passed"] for c in limits_checks)

    def test_token_budget_blocks_tool(self):
        from src.agent.nodes.pre_tool_gate import pre_tool_gate_node

        # Exhaust token budget (customer: 20K)
        self.svc.track_token_usage("gate-tokens", 15_000, 6_000, "default")

        state = {
            "session_id": "gate-tokens",
            "user_role": "customer",
            "message": "check",
            "chat_history": [],
            "allowed_tools": ["getOrderStatus"],
            "tool_plan": [{"tool": "getOrderStatus", "args": {"order_id": "ORD-001"}}],
            "tool_calls": [],
            "iterations": 0,
        }
        result = pre_tool_gate_node(state)
        decisions = result["gate_decisions"]
        assert decisions[0]["decision"] == "BLOCK"
        assert "max_tokens_per_session" in decisions[0]["reason"]

    def test_tool_calls_incremented_on_allow(self):
        """Allowed tool calls should be tracked in limits service."""
        from src.agent.nodes.pre_tool_gate import pre_tool_gate_node

        state = {
            "session_id": "gate-track",
            "user_role": "customer",
            "message": "check",
            "chat_history": [],
            "allowed_tools": ["getOrderStatus"],
            "tool_plan": [{"tool": "getOrderStatus", "args": {"order_id": "ORD-001"}}],
            "tool_calls": [],
            "iterations": 0,
        }
        pre_tool_gate_node(state)
        usage = self.svc.get_session_usage("gate-track")
        assert usage["session_tool_calls"] == 1


# ══════════════════════════════════════════════════════════════════════
# Integration — Graph Limit Short-Circuit
# ══════════════════════════════════════════════════════════════════════


class TestGraphLimitRouting:
    """Test that graph routes correctly when limits are exceeded."""

    def test_after_input_routes_to_memory_on_limit(self):
        from src.agent.graph import _after_input

        state = {"limit_exceeded": "max_requests_per_minute", "final_response": "limit msg"}
        assert _after_input(state) == "memory"

    def test_after_input_routes_to_intent_normally(self):
        from src.agent.graph import _after_input

        state = {"limit_exceeded": None}
        assert _after_input(state) == "intent"

    def test_after_input_routes_to_intent_when_missing(self):
        from src.agent.graph import _after_input

        state = {}
        assert _after_input(state) == "intent"

    def test_check_blocked_routes_on_limit_exceeded(self):
        from src.agent.graph import _check_blocked

        state = {"limit_exceeded": "max_tokens_per_session", "firewall_decision": {"decision": "ALLOW"}}
        assert _check_blocked(state) == "memory"

    def test_check_blocked_normal(self):
        from src.agent.graph import _check_blocked

        state = {"limit_exceeded": None, "firewall_decision": {"decision": "ALLOW"}}
        assert _check_blocked(state) == "response"


# ══════════════════════════════════════════════════════════════════════
# Edge Cases
# ══════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        self.svc = LimitsService()

    def test_zero_tokens_tracked(self):
        result = self.svc.track_token_usage("s1", 0, 0)
        assert result["session_tokens_in"] == 0
        assert result["cost_delta"] == 0.0

    def test_unknown_model_uses_default_pricing(self):
        result = self.svc.track_token_usage("s1", 1000, 1000, "some-unknown-model")
        expected = (1000 / 1000 * 0.0005) + (1000 / 1000 * 0.0015)
        assert abs(result["cost_delta"] - expected) < 1e-8

    def test_limit_ok_is_allowed(self):
        assert LIMIT_OK.allowed is True
        assert LIMIT_OK.limit_type is None

    def test_limit_exceeded_message_set(self):
        assert "maximum" in LIMIT_EXCEEDED_MESSAGE.lower()
        assert "try" in LIMIT_EXCEEDED_MESSAGE.lower()

    def test_multiple_sessions_independent_budgets(self):
        self.svc.track_token_usage("s1", 10_000, 5_000)
        self.svc.track_token_usage("s2", 100, 50)
        config = LimitsConfig(max_tokens_per_session=20_000)
        assert self.svc.check_token_budget("s1", config).allowed is True
        assert self.svc.check_token_budget("s2", config).allowed is True

    def test_singleton_returns_same_instance(self):
        import src.agent.limits.service as svc_mod

        svc_mod._service = None
        s1 = get_limits_service()
        s2 = get_limits_service()
        assert s1 is s2
        # Reset for other tests
        svc_mod._service = None
