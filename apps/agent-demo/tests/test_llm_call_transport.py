"""Transport-level tests for llm_call_node — verify arguments to acompletion.

Previous tests mocked `acompletion` at the function level with a pre-built
AsyncMock response, never verifying WHAT was passed to it (model name,
messages, temperature, api_key/api_base, timeout).

These tests still mock `acompletion` (we can't call real LLM providers in
CI), but they inspect `.call_args` to verify the full parameter set — the
same class of bug as the double-/v1/ URL would surface as wrong model
prefix, missing api_key, wrong temperature, etc.

Scan layer uses `httpx_mock` (transport-level) so URL construction is also
exercised end-to-end.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.agent.nodes.llm_call import llm_call_node

# ── Helpers ──────────────────────────────────────────────────

_ACOMPLETION_PATCH = "src.agent.nodes.llm_call.acompletion"


def _scan_allow_json() -> dict:
    return {
        "decision": "ALLOW",
        "risk_score": 0.1,
        "risk_flags": {},
        "intent": "qa",
        "blocked_reason": None,
        "scanner_results": None,
        "node_timings": {},
    }


def _scan_block_json() -> dict:
    return {
        "decision": "BLOCK",
        "risk_score": 0.9,
        "risk_flags": {"suspicious_intent": 0.8},
        "intent": "jailbreak",
        "blocked_reason": "Jailbreak attempt detected.",
        "scanner_results": None,
        "node_timings": {},
    }


def _mock_llm_response(content: str = "Test LLM response"):
    resp = AsyncMock()
    resp.choices = [AsyncMock()]
    resp.choices[0].message.content = content
    resp.usage = AsyncMock()
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 25
    resp.usage.total_tokens = 125
    return resp


def _base_state(**overrides) -> dict:
    state = {
        "session_id": "test-transport-1",
        "user_role": "customer",
        "message": "What is your return policy?",
        "chat_history": [],
        "api_key": "sk-test-key-123",
        "model": "gpt-4o",
        "policy": "balanced",
    }
    state.update(overrides)
    return state


# ── Test: acompletion receives correct model + kwargs ────────


class TestAcompletionModelRouting:
    """Verify acompletion is called with correct model prefix and kwargs."""

    @pytest.mark.asyncio
    async def test_openai_model_no_prefix(self, httpx_mock):
        """OpenAI models should be passed as-is (no prefix)."""
        httpx_mock.add_response(json=_scan_allow_json(), status_code=200)
        llm = _mock_llm_response()

        with patch(_ACOMPLETION_PATCH, return_value=llm) as mock_acomp:
            await llm_call_node(_base_state(model="gpt-4o", api_key="sk-openai"))

        mock_acomp.assert_called_once()
        call_kwargs = mock_acomp.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o"
        assert call_kwargs.kwargs["api_key"] == "sk-openai"
        assert "api_base" not in call_kwargs.kwargs

    @pytest.mark.asyncio
    async def test_google_model_gets_prefix(self, httpx_mock):
        """Google models should be prefixed with 'gemini/'."""
        httpx_mock.add_response(json=_scan_allow_json(), status_code=200)
        llm = _mock_llm_response()

        with patch(_ACOMPLETION_PATCH, return_value=llm) as mock_acomp:
            await llm_call_node(_base_state(model="gemini-2.0-flash", api_key="goog-key"))

        call_kwargs = mock_acomp.call_args
        assert call_kwargs.kwargs["model"] == "gemini/gemini-2.0-flash"
        assert call_kwargs.kwargs["api_key"] == "goog-key"

    @pytest.mark.asyncio
    async def test_anthropic_model_gets_prefix(self, httpx_mock):
        """Anthropic models should be prefixed with 'anthropic/'."""
        httpx_mock.add_response(json=_scan_allow_json(), status_code=200)
        llm = _mock_llm_response()

        with patch(_ACOMPLETION_PATCH, return_value=llm) as mock_acomp:
            await llm_call_node(_base_state(model="claude-sonnet-4-6", api_key="sk-ant"))

        call_kwargs = mock_acomp.call_args
        assert call_kwargs.kwargs["model"] == "anthropic/claude-sonnet-4-6"
        assert call_kwargs.kwargs["api_key"] == "sk-ant"

    @pytest.mark.asyncio
    async def test_ollama_model_gets_prefix_and_api_base(self, httpx_mock):
        """Ollama models should get 'ollama/' prefix + api_base (no api_key)."""
        httpx_mock.add_response(json=_scan_allow_json(), status_code=200)
        llm = _mock_llm_response()

        with patch(_ACOMPLETION_PATCH, return_value=llm) as mock_acomp:
            await llm_call_node(_base_state(model="llama3.1:8b", api_key="irrelevant"))

        call_kwargs = mock_acomp.call_args
        assert call_kwargs.kwargs["model"] == "ollama/llama3.1:8b"
        assert "api_base" in call_kwargs.kwargs
        assert "api_key" not in call_kwargs.kwargs

    @pytest.mark.asyncio
    async def test_mistral_model_gets_prefix(self, httpx_mock):
        httpx_mock.add_response(json=_scan_allow_json(), status_code=200)
        llm = _mock_llm_response()

        with patch(_ACOMPLETION_PATCH, return_value=llm) as mock_acomp:
            await llm_call_node(_base_state(model="mistral-large-latest", api_key="ms-key"))

        call_kwargs = mock_acomp.call_args
        assert call_kwargs.kwargs["model"] == "mistral/mistral-large-latest"
        assert call_kwargs.kwargs["api_key"] == "ms-key"


# ── Test: acompletion receives correct messages + params ─────


class TestAcompletionParams:
    """Verify temperature, max_tokens, timeout, and messages are correct."""

    @pytest.mark.asyncio
    async def test_temperature_and_max_tokens(self, httpx_mock):
        httpx_mock.add_response(json=_scan_allow_json(), status_code=200)
        llm = _mock_llm_response()

        with patch(_ACOMPLETION_PATCH, return_value=llm) as mock_acomp:
            await llm_call_node(_base_state(model="gpt-4o", api_key="sk-test"))

        call_kwargs = mock_acomp.call_args.kwargs
        # These come from settings defaults
        assert isinstance(call_kwargs["temperature"], float)
        assert isinstance(call_kwargs["max_tokens"], int)
        assert call_kwargs["timeout"] == 120

    @pytest.mark.asyncio
    async def test_messages_include_system_prompt(self, httpx_mock):
        """acompletion should receive full messages (with system prompt)."""
        httpx_mock.add_response(json=_scan_allow_json(), status_code=200)
        llm = _mock_llm_response()

        with patch(_ACOMPLETION_PATCH, return_value=llm) as mock_acomp:
            await llm_call_node(_base_state(model="gpt-4o", api_key="sk-test"))

        messages = mock_acomp.call_args.kwargs["messages"]
        # build_messages should produce at least system + user messages
        assert len(messages) >= 2
        roles = [m["role"] for m in messages]
        assert "system" in roles
        assert "user" in roles


# ── Test: scan URL exercised at transport level ──────────────


class TestScanTransportLayer:
    """httpx_mock verifies the scan URL + headers are correct end-to-end."""

    @pytest.mark.asyncio
    async def test_scan_url_and_headers(self, httpx_mock):
        """llm_call_node should hit /scan (not /v1/scan) on proxy_base_url."""
        httpx_mock.add_response(json=_scan_allow_json(), status_code=200)
        llm = _mock_llm_response()

        with patch(_ACOMPLETION_PATCH, return_value=llm):
            await llm_call_node(
                _base_state(
                    session_id="scan-check-1",
                    model="gpt-4o",
                    api_key="sk-test",
                    policy="strict",
                )
            )

        req = httpx_mock.get_request()
        assert req is not None
        # Must be /v1/scan (proxy_base_url=http://localhost:8000/v1 + /scan)
        assert str(req.url).endswith("/v1/scan")
        assert req.headers["x-policy"] == "strict"
        assert req.headers["x-correlation-id"] == "scan-check-1"
        assert req.headers["x-api-key"] == "sk-test"

    @pytest.mark.asyncio
    async def test_scan_body_contains_user_message(self, httpx_mock):
        """Scan body should contain the user message (not system prompt)."""
        httpx_mock.add_response(json=_scan_allow_json(), status_code=200)
        llm = _mock_llm_response()

        with patch(_ACOMPLETION_PATCH, return_value=llm):
            await llm_call_node(
                _base_state(
                    message="Tell me about refunds",
                    model="gpt-4o",
                    api_key="sk-test",
                )
            )

        req = httpx_mock.get_request()
        body = json.loads(req.content)
        messages = body["messages"]
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert any("refunds" in m["content"] for m in user_msgs)

    @pytest.mark.asyncio
    async def test_scan_block_stops_llm_call(self, httpx_mock):
        """When scan returns BLOCK (403), acompletion must NOT be called."""
        httpx_mock.add_response(json=_scan_block_json(), status_code=403)

        with patch(_ACOMPLETION_PATCH) as mock_acomp:
            result = await llm_call_node(_base_state(model="gpt-4o", api_key="sk-test"))

        mock_acomp.assert_not_called()
        assert result["firewall_decision"]["decision"] == "BLOCK"
        assert "can't process" in result["final_response"].lower()


# ── Test: result propagation ─────────────────────────────────


class TestResultPropagation:
    """Verify LLM response and firewall decision are correctly propagated."""

    @pytest.mark.asyncio
    async def test_llm_response_in_state(self, httpx_mock):
        httpx_mock.add_response(json=_scan_allow_json(), status_code=200)
        llm = _mock_llm_response("The return policy is 30 days.")

        with patch(_ACOMPLETION_PATCH, return_value=llm):
            result = await llm_call_node(_base_state(model="gpt-4o", api_key="sk-test"))

        assert result["llm_response"] == "The return policy is 30 days."
        assert result["firewall_decision"]["decision"] == "ALLOW"
        assert result["firewall_decision"]["intent"] == "qa"

    @pytest.mark.asyncio
    async def test_trace_contains_firewall(self, httpx_mock):
        httpx_mock.add_response(json=_scan_allow_json(), status_code=200)
        llm = _mock_llm_response()

        with patch(_ACOMPLETION_PATCH, return_value=llm):
            result = await llm_call_node(_base_state(model="gpt-4o", api_key="sk-test"))

        trace = result.get("trace", {})
        # Trace stores LLM call data inside iterations[0]
        iterations = trace.get("iterations", [])
        assert len(iterations) >= 1
        llm_trace = iterations[0].get("llm_call", {})
        assert llm_trace.get("messages_count", 0) >= 2
        fw = iterations[0].get("firewall_decision", {})
        assert fw["decision"] == "ALLOW"
