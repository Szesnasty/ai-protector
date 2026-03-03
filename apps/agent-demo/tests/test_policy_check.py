"""Tests for PolicyCheckNode — RBAC tool filtering."""

from src.agent.nodes.policy import policy_check_node
from src.agent.tools.registry import get_allowed_tools


class TestGetAllowedTools:
    def test_customer_tools(self):
        tools = get_allowed_tools("customer")
        assert "searchKnowledgeBase" in tools
        assert "getOrderStatus" in tools
        assert "getInternalSecrets" not in tools

    def test_admin_tools(self):
        tools = get_allowed_tools("admin")
        assert "searchKnowledgeBase" in tools
        assert "getOrderStatus" in tools
        assert "getInternalSecrets" in tools

    def test_unknown_role(self):
        tools = get_allowed_tools("hacker")
        assert tools == []


class TestPolicyCheckNode:
    def test_customer_state(self):
        state = {"user_role": "customer"}
        result = policy_check_node(state)
        assert "getInternalSecrets" not in result["allowed_tools"]
        assert "searchKnowledgeBase" in result["allowed_tools"]

    def test_admin_state(self):
        state = {"user_role": "admin"}
        result = policy_check_node(state)
        assert "getInternalSecrets" in result["allowed_tools"]
