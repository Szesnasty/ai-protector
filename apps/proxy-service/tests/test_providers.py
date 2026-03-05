"""Tests for provider detection and LiteLLM routing."""

import pytest

from src.llm.providers import detect_provider, format_litellm_model


# ── detect_provider ──────────────────────────────────────────────

class TestDetectProvider:
    """Test provider detection from model names."""

    @pytest.mark.parametrize(
        "model, expected",
        [
            ("gpt-4o", "openai"),
            ("gpt-4o-mini", "openai"),
            ("gpt-4-turbo", "openai"),
            ("GPT-4o", "openai"),  # case-insensitive
            ("o1", "openai"),
            ("o3-mini", "openai"),
        ],
    )
    @pytest.mark.asyncio
    async def test_openai(self, model: str, expected: str) -> None:
        assert detect_provider(model) == expected

    @pytest.mark.parametrize(
        "model, expected",
        [
            ("claude-sonnet-4-6", "anthropic"),
            ("claude-haiku-4-5", "anthropic"),
            ("anthropic/claude-sonnet-4-6", "anthropic"),
        ],
    )
    @pytest.mark.asyncio
    async def test_anthropic(self, model: str, expected: str) -> None:
        assert detect_provider(model) == expected

    @pytest.mark.parametrize(
        "model, expected",
        [
            ("gemini/gemini-2.5-flash", "google"),
            ("gemini/gemini-pro", "google"),
        ],
    )
    @pytest.mark.asyncio
    async def test_google(self, model: str, expected: str) -> None:
        assert detect_provider(model) == expected

    @pytest.mark.parametrize(
        "model, expected",
        [
            ("mistral-large", "mistral"),
            ("codestral", "mistral"),
            ("mistral/mistral-large", "mistral"),
        ],
    )
    @pytest.mark.asyncio
    async def test_mistral(self, model: str, expected: str) -> None:
        assert detect_provider(model) == expected

    @pytest.mark.parametrize(
        "model, expected",
        [
            ("ollama/llama3.1:8b", "ollama"),
            ("ollama/phi3:mini", "ollama"),
        ],
    )
    @pytest.mark.asyncio
    async def test_ollama_explicit(self, model: str, expected: str) -> None:
        assert detect_provider(model) == expected

    @pytest.mark.asyncio
    async def test_unknown_defaults_to_ollama(self) -> None:
        assert detect_provider("my-custom-model") == "ollama"
        assert detect_provider("llama3.1:8b") == "ollama"


# ── format_litellm_model ──────────────────────────────────────────

class TestFormatLitellmModel:
    """Test model name formatting for LiteLLM."""

    @pytest.mark.asyncio
    async def test_openai_no_prefix(self) -> None:
        assert format_litellm_model("gpt-4o", "openai") == "gpt-4o"

    @pytest.mark.asyncio
    async def test_ollama_adds_prefix(self) -> None:
        assert format_litellm_model("llama3.1:8b", "ollama") == "ollama/llama3.1:8b"

    @pytest.mark.asyncio
    async def test_ollama_already_prefixed(self) -> None:
        assert format_litellm_model("ollama/llama3.1:8b", "ollama") == "ollama/llama3.1:8b"

    @pytest.mark.asyncio
    async def test_anthropic_adds_prefix(self) -> None:
        assert format_litellm_model("claude-sonnet-4-6", "anthropic") == "anthropic/claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_anthropic_already_prefixed(self) -> None:
        assert format_litellm_model("anthropic/claude-sonnet-4-6", "anthropic") == "anthropic/claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_google_adds_prefix(self) -> None:
        assert format_litellm_model("gemini-2.5-flash", "google") == "gemini/gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_google_already_prefixed(self) -> None:
        assert format_litellm_model("gemini/gemini-2.5-flash", "google") == "gemini/gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_mistral_adds_prefix(self) -> None:
        assert format_litellm_model("mistral-large", "mistral") == "mistral/mistral-large"

    @pytest.mark.asyncio
    async def test_mistral_already_prefixed(self) -> None:
        assert format_litellm_model("mistral/mistral-large", "mistral") == "mistral/mistral-large"
