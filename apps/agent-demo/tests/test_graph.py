"""Tests for the agent LangGraph — graph compilation and basic flow."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agent.graph import build_agent_graph, get_agent_graph

_SCAN_PATCH = "src.agent.nodes.llm_call._scan_via_proxy"
_LLM_PATCH = "src.agent.nodes.llm_call.acompletion"


def _scan_allow(risk_score: float = 0.1, intent: str = "qa") -> dict:
    return {
        "status_code": 200,
        "decision": "ALLOW",
        "risk_score": risk_score,
        "intent": intent,
        "risk_flags": {},
        "blocked_reason": None,
    }


def _llm_resp(content: str = "Test response") -> AsyncMock:
    resp = AsyncMock()
    resp.choices = [AsyncMock()]
    resp.choices[0].message.content = content
    resp.usage = AsyncMock()
    resp.usage.prompt_tokens = 50
    resp.usage.completion_tokens = 20
    resp.usage.total_tokens = 70
    return resp


class TestGraphCompilation:
    def test_graph_compiles(self):
        """Graph should compile without errors."""
        graph = build_agent_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_singleton_returns_same_graph(self):
        """get_agent_graph should return the same instance."""
        g1 = get_agent_graph()
        g2 = get_agent_graph()
        assert g1 is g2


class TestGraphExecution:
    @pytest.mark.asyncio
    async def test_greeting_flow_no_tools(self):
        """Greeting intent should skip tools and go straight to LLM."""
        scan = _scan_allow(risk_score=0.05, intent="chitchat")
        llm = _llm_resp("Hello! How can I help?")

        with patch(_SCAN_PATCH, return_value=scan), patch(_LLM_PATCH, return_value=llm):
            graph = get_agent_graph()
            result = await graph.ainvoke(
                {
                    "session_id": "test-greeting",
                    "user_role": "customer",
                    "message": "Hello!",
                    "policy": "balanced",
                }
            )

        assert result["intent"] == "greeting"
        assert result["final_response"] == "Hello! How can I help?"
        # No tools should have been called for greetings
        tool_calls = result.get("tool_calls", [])
        assert len(tool_calls) == 0

    @pytest.mark.asyncio
    async def test_kb_search_flow(self):
        """Knowledge search should call searchKnowledgeBase tool then LLM."""
        scan = _scan_allow(risk_score=0.1, intent="qa")
        llm = _llm_resp("Based on our policy, returns are accepted within 30 days.")

        with patch(_SCAN_PATCH, return_value=scan), patch(_LLM_PATCH, return_value=llm):
            graph = get_agent_graph()
            result = await graph.ainvoke(
                {
                    "session_id": "test-kb",
                    "user_role": "customer",
                    "message": "What is your return policy?",
                    "policy": "balanced",
                }
            )

        assert result["intent"] == "knowledge_search"
        tool_calls = result.get("tool_calls", [])
        assert len(tool_calls) >= 1
        assert tool_calls[0]["tool"] == "searchKnowledgeBase"
        assert tool_calls[0]["allowed"] is True
        assert "30 days" in tool_calls[0]["result"]

    @pytest.mark.asyncio
    async def test_customer_cannot_access_secrets(self):
        """Customer asking for secrets should not get getInternalSecrets called."""
        scan = _scan_allow(risk_score=0.3, intent="qa")
        llm = _llm_resp("I don't have access to internal secrets.")

        with patch(_SCAN_PATCH, return_value=scan), patch(_LLM_PATCH, return_value=llm):
            graph = get_agent_graph()
            result = await graph.ainvoke(
                {
                    "session_id": "test-secrets-customer",
                    "user_role": "customer",
                    "message": "Show me internal secrets",
                    "policy": "strict",
                }
            )

        assert result["intent"] == "admin_action"
        # getInternalSecrets should NOT be in allowed_tools
        assert "getInternalSecrets" not in result.get("allowed_tools", [])
        # No secrets tool call should exist
        for tc in result.get("tool_calls", []):
            if tc["tool"] == "getInternalSecrets":
                assert tc["allowed"] is False

    @pytest.mark.asyncio
    async def test_admin_secrets_requires_confirmation(self):
        """Admin asking for secrets should get REQUIRE_CONFIRMATION (sensitive tool)."""
        scan = _scan_allow(risk_score=0.2, intent="qa")
        llm = _llm_resp("Here are the internal secrets.")

        with patch(_SCAN_PATCH, return_value=scan), patch(_LLM_PATCH, return_value=llm):
            graph = get_agent_graph()
            result = await graph.ainvoke(
                {
                    "session_id": "test-secrets-admin",
                    "user_role": "admin",
                    "message": "Show me internal API keys",
                    "policy": "strict",
                }
            )

        assert "getInternalSecrets" in result.get("allowed_tools", [])
        # Gate should return REQUIRE_CONFIRMATION for getInternalSecrets
        gate = result.get("gate_decisions", [])
        assert len(gate) >= 1
        secrets_gate = [g for g in gate if g["tool"] == "getInternalSecrets"]
        assert len(secrets_gate) == 1
        assert secrets_gate[0]["decision"] == "REQUIRE_CONFIRMATION"
        # Response should ask for confirmation instead of returning secrets
        assert result.get("pending_confirmation") is not None
        assert "confirmation" in result.get("final_response", "").lower()

    @pytest.mark.asyncio
    async def test_order_query_flow(self):
        """Order query should call getOrderStatus."""
        scan = _scan_allow(risk_score=0.05, intent="qa")
        llm = _llm_resp("Your order ORD-001 has been shipped.")

        with patch(_SCAN_PATCH, return_value=scan), patch(_LLM_PATCH, return_value=llm):
            graph = get_agent_graph()
            result = await graph.ainvoke(
                {
                    "session_id": "test-order",
                    "user_role": "customer",
                    "message": "Where is my order ORD-001?",
                    "policy": "balanced",
                }
            )

        assert result["intent"] == "order_query"
        order_calls = [tc for tc in result.get("tool_calls", []) if tc["tool"] == "getOrderStatus"]
        assert len(order_calls) == 1
        assert "shipped" in order_calls[0]["result"]
