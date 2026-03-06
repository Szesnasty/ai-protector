"""Tests for agent-demo mock LLM (demo mode)."""

from __future__ import annotations

import pytest

from src.agent.mock_llm import (
    GENERAL_RESPONSES,
    mock_agent_llm,
)


def _base_state(**overrides) -> dict:
    """Build a minimal AgentState for testing."""
    state = {
        "messages": [{"role": "user", "content": "hello"}],
        "session_id": "test-session",
        "user_role": "customer",
        "trace": [],
    }
    state.update(overrides)
    return state


class TestMockAgentLlm:
    """Test the agent-demo mock LLM."""

    def test_general_response_for_generic_message(self) -> None:
        state = _base_state(messages=[{"role": "user", "content": "hi there"}])
        result = mock_agent_llm(state)

        assert result["llm_response"] in GENERAL_RESPONSES
        assert result["firewall_decision"]["decision"] == "ALLOW"

    def test_tool_call_triggered_by_order_keyword(self) -> None:
        state = _base_state(
            messages=[{"role": "user", "content": "Check my order status please"}]
        )
        result = mock_agent_llm(state)

        # Should return empty content (tool call scenario)
        assert result["llm_response"] == ""

    def test_tool_call_triggered_by_return_keyword(self) -> None:
        state = _base_state(
            messages=[{"role": "user", "content": "What is your return policy?"}]
        )
        result = mock_agent_llm(state)

        # return keyword triggers searchKnowledgeBase
        assert result["llm_response"] == ""

    def test_summary_when_tool_results_present(self) -> None:
        state = _base_state(
            messages=[
                {"role": "user", "content": "Check order ORD-123"},
                {"role": "assistant", "content": ""},
                {"role": "tool", "content": "Order ORD-123: shipped, ETA 2 days"},
            ]
        )
        result = mock_agent_llm(state)

        # Should contain some part of the tool result in the summary
        assert "Order ORD-123" in result["llm_response"] or "found" in result["llm_response"].lower()

    def test_state_preserved(self) -> None:
        state = _base_state(
            messages=[{"role": "user", "content": "hello"}],
            session_id="s-999",
            user_role="admin",
        )
        result = mock_agent_llm(state)

        assert result["session_id"] == "s-999"
        assert result["user_role"] == "admin"
        assert "llm_messages" in result
        assert "firewall_decision" in result

    def test_firewall_decision_structure(self) -> None:
        state = _base_state()
        result = mock_agent_llm(state)

        fd = result["firewall_decision"]
        assert fd["decision"] == "ALLOW"
        assert fd["risk_score"] == 0.0
        assert isinstance(fd["risk_flags"], dict)
