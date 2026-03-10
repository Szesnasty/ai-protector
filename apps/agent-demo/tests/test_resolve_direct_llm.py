"""Tests for _resolve_direct_llm — provider detection and model formatting.

The agent mirrors proxy-service/src/llm/providers.py detection rules.
These tests ensure the agent's copy stays in sync: wrong prefixes or
missing providers would silently send requests to the wrong provider,
resulting in 401/404 errors from the LLM API.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.agent.nodes.llm_call import _PROVIDER_RULES, _resolve_direct_llm

# ── Helpers ──────────────────────────────────────────────────


def _settings(ollama_base_url: str = "http://localhost:11434") -> MagicMock:
    s = MagicMock()
    s.ollama_base_url = ollama_base_url
    return s


# ── Provider detection rules ────────────────────────────────


class TestProviderRules:
    """Verify _PROVIDER_RULES matches proxy-service/src/llm/providers.py."""

    # The authoritative list from proxy-service
    PROXY_RULES = [
        ("ollama/", "ollama"),
        ("anthropic/", "anthropic"),
        ("gemini/", "google"),
        ("mistral/", "mistral"),
        ("azure/", "azure"),
        ("gpt-", "openai"),
        ("o1", "openai"),
        ("o3", "openai"),
        ("claude-", "anthropic"),
        ("gemini-", "google"),
        ("mistral-", "mistral"),
        ("codestral", "mistral"),
    ]

    def test_rules_match_proxy_service(self):
        """Agent rules must be identical to proxy-service rules.

        If you update proxy-service/src/llm/providers.py:PROVIDER_RULES,
        you MUST update _PROVIDER_RULES in llm_call.py as well.
        """
        assert _PROVIDER_RULES == self.PROXY_RULES, (
            "Agent _PROVIDER_RULES diverged from proxy-service PROVIDER_RULES! "
            "Update apps/agent-demo/src/agent/nodes/llm_call.py to match."
        )


# ── Ollama models (local, no API key) ───────────────────────


class TestOllamaModels:
    """Ollama models → prefix with 'ollama/' + use api_base."""

    def test_bare_model_name(self):
        model, kwargs = _resolve_direct_llm("llama3.1:8b", None, _settings())
        assert model == "ollama/llama3.1:8b"
        assert kwargs == {"api_base": "http://localhost:11434"}

    def test_already_prefixed(self):
        model, kwargs = _resolve_direct_llm("ollama/llama3.1:8b", None, _settings())
        assert model == "ollama/llama3.1:8b"
        assert kwargs == {"api_base": "http://localhost:11434"}

    def test_custom_ollama_url(self):
        model, kwargs = _resolve_direct_llm("mistral:7b", None, _settings("http://gpu-box:11434"))
        assert model == "ollama/mistral:7b"
        assert kwargs == {"api_base": "http://gpu-box:11434"}

    def test_unknown_model_defaults_ollama(self):
        """Unrecognized model names default to ollama provider."""
        model, kwargs = _resolve_direct_llm("my-custom-model", None, _settings())
        assert model == "ollama/my-custom-model"
        assert "api_base" in kwargs


# ── OpenAI models (no prefix needed) ────────────────────────


class TestOpenAIModels:
    """OpenAI models → as-is (no prefix), use api_key."""

    @pytest.mark.parametrize(
        "model_name",
        ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    )
    def test_gpt_models(self, model_name):
        model, kwargs = _resolve_direct_llm(model_name, "sk-test", _settings())
        assert model == model_name  # no prefix
        assert kwargs == {"api_key": "sk-test"}

    @pytest.mark.parametrize("model_name", ["o1", "o1-mini", "o3-mini"])
    def test_o_series_models(self, model_name):
        model, kwargs = _resolve_direct_llm(model_name, "sk-test", _settings())
        assert model == model_name
        assert kwargs == {"api_key": "sk-test"}


# ── Anthropic models ────────────────────────────────────────


class TestAnthropicModels:
    """Anthropic models → prefix with 'anthropic/'."""

    @pytest.mark.parametrize(
        "model_name,expected",
        [
            ("claude-sonnet-4-6", "anthropic/claude-sonnet-4-6"),
            ("claude-haiku-4-5", "anthropic/claude-haiku-4-5"),
            ("claude-opus-4-6", "anthropic/claude-opus-4-6"),
            ("anthropic/claude-sonnet-4-6", "anthropic/claude-sonnet-4-6"),
        ],
    )
    def test_anthropic_models(self, model_name, expected):
        model, kwargs = _resolve_direct_llm(model_name, "sk-ant-test", _settings())
        assert model == expected
        assert kwargs == {"api_key": "sk-ant-test"}


# ── Google models ────────────────────────────────────────────


class TestGoogleModels:
    """Google models → prefix with 'gemini/'."""

    @pytest.mark.parametrize(
        "model_name,expected",
        [
            ("gemini-2.0-flash", "gemini/gemini-2.0-flash"),
            ("gemini-2.5-pro", "gemini/gemini-2.5-pro"),
            ("gemini-2.5-flash", "gemini/gemini-2.5-flash"),
            ("gemini/gemini-2.0-flash", "gemini/gemini-2.0-flash"),
        ],
    )
    def test_google_models(self, model_name, expected):
        model, kwargs = _resolve_direct_llm(model_name, "ai-key", _settings())
        assert model == expected
        assert kwargs == {"api_key": "ai-key"}


# ── Mistral models ───────────────────────────────────────────


class TestMistralModels:
    """Mistral models → prefix with 'mistral/'."""

    @pytest.mark.parametrize(
        "model_name,expected",
        [
            ("mistral-large-latest", "mistral/mistral-large-latest"),
            ("mistral-small-latest", "mistral/mistral-small-latest"),
            ("codestral-latest", "mistral/codestral-latest"),
            ("mistral/mistral-large-latest", "mistral/mistral-large-latest"),
        ],
    )
    def test_mistral_models(self, model_name, expected):
        model, kwargs = _resolve_direct_llm(model_name, "ms-key", _settings())
        assert model == expected
        assert kwargs == {"api_key": "ms-key"}


# ── API key forwarding ──────────────────────────────────────


class TestAPIKeyForwarding:
    """Verify api_key is correctly forwarded for external providers."""

    def test_no_api_key_ollama(self):
        """Ollama should work without API key."""
        _, kwargs = _resolve_direct_llm("llama3.1:8b", None, _settings())
        assert "api_key" not in kwargs
        assert "api_base" in kwargs

    def test_api_key_forwarded_to_openai(self):
        _, kwargs = _resolve_direct_llm("gpt-4o", "sk-real-key-123", _settings())
        assert kwargs["api_key"] == "sk-real-key-123"

    def test_api_key_forwarded_to_anthropic(self):
        _, kwargs = _resolve_direct_llm("claude-sonnet-4-6", "sk-ant-key", _settings())
        assert kwargs["api_key"] == "sk-ant-key"

    def test_api_key_forwarded_to_google(self):
        _, kwargs = _resolve_direct_llm("gemini-2.0-flash", "goog-key", _settings())
        assert kwargs["api_key"] == "goog-key"

    def test_none_api_key_for_external_provider(self):
        """Even with None api_key, external providers get api_key in kwargs."""
        _, kwargs = _resolve_direct_llm("gpt-4o", None, _settings())
        assert kwargs == {"api_key": None}
