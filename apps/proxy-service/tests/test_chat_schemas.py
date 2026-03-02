"""Tests for OpenAI-compatible chat schemas."""

import pytest
from pydantic import ValidationError

from src.schemas.chat import (
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Usage,
)

# ── ChatCompletionRequest ───────────────────────────────────────────


class TestChatCompletionRequest:
    """Validate ChatCompletionRequest parsing and constraints."""

    def test_minimal_valid(self):
        req = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="Hello")]
        )
        assert req.model == "llama3.1:8b"
        assert req.stream is False
        assert req.temperature == 0.7
        assert len(req.messages) == 1

    def test_all_optional_fields(self):
        req = ChatCompletionRequest(
            model="mistral:7b",
            messages=[
                ChatMessage(role="system", content="You are a bot."),
                ChatMessage(role="user", content="Hi"),
            ],
            temperature=1.5,
            max_tokens=1024,
            stream=True,
            top_p=0.9,
            frequency_penalty=0.5,
            presence_penalty=0.5,
        )
        assert req.model == "mistral:7b"
        assert req.stream is True
        assert req.temperature == 1.5
        assert req.max_tokens == 1024

    def test_rejects_empty_messages(self):
        with pytest.raises(ValidationError, match="List should have at least 1 item"):
            ChatCompletionRequest(messages=[])

    def test_rejects_no_user_message(self):
        with pytest.raises(ValidationError, match="role 'user' is required"):
            ChatCompletionRequest(
                messages=[ChatMessage(role="system", content="system only")]
            )

    def test_rejects_temperature_too_low(self):
        with pytest.raises(ValidationError):
            ChatCompletionRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                temperature=-0.1,
            )

    def test_rejects_temperature_too_high(self):
        with pytest.raises(ValidationError):
            ChatCompletionRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                temperature=2.1,
            )

    def test_rejects_max_tokens_zero(self):
        with pytest.raises(ValidationError):
            ChatCompletionRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                max_tokens=0,
            )


# ── ChatCompletionResponse ──────────────────────────────────────────


class TestChatCompletionResponse:
    """Validate ChatCompletionResponse serialization."""

    def test_round_trip(self):
        resp = ChatCompletionResponse(
            id="chatcmpl-abc123",
            created=1700000000,
            model="llama3.1:8b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hello!"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )
        data = resp.model_dump()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hello!"
        assert data["usage"]["total_tokens"] == 8

        # Re-parse from dict
        parsed = ChatCompletionResponse.model_validate(data)
        assert parsed.id == resp.id
        assert parsed.choices[0].finish_reason == "stop"

    def test_no_usage(self):
        resp = ChatCompletionResponse(
            id="chatcmpl-abc123",
            created=1700000000,
            model="llama3.1:8b",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hi"),
                )
            ],
        )
        assert resp.usage is None
