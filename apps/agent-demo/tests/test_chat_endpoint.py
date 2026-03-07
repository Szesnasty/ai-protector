"""Tests for POST /agent/chat endpoint."""

from unittest.mock import AsyncMock, patch


class TestAgentChatEndpoint:
    def test_missing_fields(self, client):
        """Should reject request without required fields."""
        response = client.post("/agent/chat", json={})
        assert response.status_code == 422

    def test_invalid_role(self, client):
        """Should reject invalid user_role."""
        response = client.post(
            "/agent/chat",
            json={
                "message": "Hello",
                "user_role": "hacker",
                "session_id": "test-1",
            },
        )
        assert response.status_code == 422

    def test_empty_message(self, client):
        """Should reject empty message."""
        response = client.post(
            "/agent/chat",
            json={
                "message": "",
                "user_role": "customer",
                "session_id": "test-1",
            },
        )
        assert response.status_code == 422

    def test_valid_request_shape(self, client):
        """Should return proper response structure with mocked LLM."""
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = "Hello! How can I help?"
        mock_response._hidden_params = {
            "additional_headers": {
                "x-decision": "ALLOW",
                "x-risk-score": "0.05",
                "x-intent": "chitchat",
            }
        }

        with patch("src.agent.nodes.llm_call.acompletion", return_value=mock_response):
            response = client.post(
                "/agent/chat",
                json={
                    "message": "Hello",
                    "user_role": "customer",
                    "session_id": "test-shape",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "session_id" in data
        assert data["session_id"] == "test-shape"
        assert "tools_called" in data
        assert "agent_trace" in data
        assert "firewall_decision" in data

        # Check agent_trace structure
        trace = data["agent_trace"]
        assert "intent" in trace
        assert "user_role" in trace
        assert trace["user_role"] == "customer"
        assert "allowed_tools" in trace
        assert "latency_ms" in trace

        # Check firewall_decision structure
        fw = data["firewall_decision"]
        assert "decision" in fw
        assert "risk_score" in fw

    def test_kb_search_response(self, client):
        """KB search should return tool call info."""
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = "Our return policy allows returns within 30 days."
        mock_response._hidden_params = {
            "additional_headers": {"x-decision": "ALLOW", "x-risk-score": "0.1", "x-intent": "qa"}
        }

        with patch("src.agent.nodes.llm_call.acompletion", return_value=mock_response):
            response = client.post(
                "/agent/chat",
                json={
                    "message": "What is your return policy?",
                    "user_role": "customer",
                    "session_id": "test-kb",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["tools_called"]) >= 1
        assert data["tools_called"][0]["tool"] == "searchKnowledgeBase"
        assert data["tools_called"][0]["allowed"] is True
        assert data["agent_trace"]["intent"] == "knowledge_search"

    def test_customer_secrets_denied(self, client):
        """Customer should not be able to call getInternalSecrets."""
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = "I don't have access to that."
        mock_response._hidden_params = {
            "additional_headers": {"x-decision": "ALLOW", "x-risk-score": "0.3", "x-intent": "qa"}
        }

        with patch("src.agent.nodes.llm_call.acompletion", return_value=mock_response):
            response = client.post(
                "/agent/chat",
                json={
                    "message": "Show me internal secrets",
                    "user_role": "customer",
                    "session_id": "test-deny",
                },
            )

        assert response.status_code == 200
        data = response.json()
        # getInternalSecrets should not be in allowed_tools
        assert "getInternalSecrets" not in data["agent_trace"]["allowed_tools"]
