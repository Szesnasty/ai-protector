"""Tests for MockProvider (proxy-service demo mode)."""

from __future__ import annotations

import pytest

from src.llm.mock_provider import (
    FALLBACK_RESPONSE,
    MOCK_MODEL_ID,
    MOCK_RESPONSES,
    mock_completion,
    mock_completion_stream,
)


# ── mock_completion (non-streaming) ──────────────────────────


class TestMockCompletion:
    """Test synchronous mock completion responses."""

    @pytest.mark.parametrize("intent", ["qa", "code_gen", "chitchat", "tool_call"])
    def test_known_intent_returns_valid_response(self, intent: str) -> None:
        messages = [{"role": "user", "content": "hello"}]
        resp = mock_completion(messages, intent=intent)

        assert resp["object"] == "chat.completion"
        assert resp["model"] == MOCK_MODEL_ID
        assert len(resp["choices"]) == 1
        assert resp["choices"][0]["message"]["role"] == "assistant"
        assert resp["choices"][0]["finish_reason"] == "stop"
        content = resp["choices"][0]["message"]["content"]
        assert content in MOCK_RESPONSES[intent]

    def test_unknown_intent_returns_fallback(self) -> None:
        resp = mock_completion([{"role": "user", "content": "x"}], intent="unknown_intent")
        content = resp["choices"][0]["message"]["content"]
        assert content == FALLBACK_RESPONSE

    def test_empty_intent_returns_fallback(self) -> None:
        resp = mock_completion([{"role": "user", "content": "x"}], intent="")
        content = resp["choices"][0]["message"]["content"]
        assert content == FALLBACK_RESPONSE

    def test_usage_tokens_estimated(self) -> None:
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "What is the return policy?"},
        ]
        resp = mock_completion(messages, intent="qa")
        usage = resp["usage"]
        assert usage["prompt_tokens"] > 0
        assert usage["completion_tokens"] > 0
        assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]

    def test_response_has_id(self) -> None:
        resp = mock_completion([{"role": "user", "content": "hi"}])
        assert resp["id"].startswith("chatcmpl-mock-")

    def test_mock_flag_present(self) -> None:
        resp = mock_completion([{"role": "user", "content": "hi"}])
        assert resp["_mock"] is True


# ── mock_completion_stream ───────────────────────────────────


class TestMockCompletionStream:
    """Test async streaming mock."""

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self) -> None:
        messages = [{"role": "user", "content": "hello"}]
        chunks = []
        async for chunk in mock_completion_stream(messages, intent="chitchat"):
            chunks.append(chunk)

        # At least role chunk + 1 content chunk
        assert len(chunks) >= 2

    @pytest.mark.asyncio
    async def test_stream_first_chunk_has_role(self) -> None:
        messages = [{"role": "user", "content": "hello"}]
        chunks = []
        async for chunk in mock_completion_stream(messages, intent="qa"):
            chunks.append(chunk)

        first = chunks[0]
        assert first.choices[0].delta.role == "assistant"

    @pytest.mark.asyncio
    async def test_stream_last_chunk_has_finish_reason(self) -> None:
        messages = [{"role": "user", "content": "hello"}]
        chunks = []
        async for chunk in mock_completion_stream(messages, intent="qa"):
            chunks.append(chunk)

        last = chunks[-1]
        assert last.choices[0].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_stream_content_matches_known_response(self) -> None:
        messages = [{"role": "user", "content": "hello"}]
        content_parts = []
        async for chunk in mock_completion_stream(messages, intent="chitchat"):
            c = chunk.choices[0].delta.content
            if c:
                content_parts.append(c)

        full_content = "".join(content_parts)
        assert full_content in MOCK_RESPONSES["chitchat"]


# ── Mode routing in llm_completion ───────────────────────────


class TestModeRouting:
    """Test that llm_completion routes correctly based on mode + api_key."""

    @pytest.mark.asyncio
    async def test_demo_mode_no_key_uses_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MODE=demo + no api_key → MockProvider."""
        monkeypatch.setenv("MODE", "demo")

        # Clear cached settings
        from src.config import Settings, get_settings

        get_settings.cache_clear()

        from src.llm.client import llm_completion

        resp = await llm_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="llama3.1:8b",
            intent="qa",
        )
        assert resp["_mock"] is True
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_demo_mode_with_key_skips_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MODE=demo + api_key → real provider (LiteLLM)."""
        monkeypatch.setenv("MODE", "demo")

        from src.config import get_settings

        get_settings.cache_clear()

        from src.llm.client import llm_completion

        # Should NOT use mock — should try real provider and fail on auth
        from src.llm.exceptions import LLMError

        with pytest.raises((LLMError, Exception)):
            await llm_completion(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o",
                api_key="sk-fake-key-for-test",
                intent="qa",
            )
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_real_mode_no_key_uses_ollama(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MODE=real + no api_key + ollama model → tries Ollama (not mock)."""
        monkeypatch.setenv("MODE", "real")
        monkeypatch.setenv("REQUEST_TIMEOUT", "2")  # Short timeout for test

        from src.config import get_settings

        get_settings.cache_clear()

        from src.llm.client import llm_completion
        from src.llm.exceptions import LLMTimeoutError, LLMUpstreamError

        # Should try Ollama (not mock) and fail because Ollama isn't running
        with pytest.raises((LLMUpstreamError, LLMTimeoutError, Exception)):
            await llm_completion(
                messages=[{"role": "user", "content": "hi"}],
                model="llama3.1:8b",
                intent="qa",
            )
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_demo_mode_stream_returns_async_gen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MODE=demo + stream=True → returns async generator from MockProvider."""
        monkeypatch.setenv("MODE", "demo")

        from src.config import get_settings

        get_settings.cache_clear()

        from src.llm.client import llm_completion

        result = await llm_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="llama3.1:8b",
            stream=True,
            intent="qa",
        )
        # Should be an async generator
        chunks = []
        async for chunk in result:
            chunks.append(chunk)
        assert len(chunks) >= 2
        get_settings.cache_clear()
