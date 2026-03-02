"""OpenAI-compatible Pydantic schemas for chat completions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# ── Request ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """A single chat message."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str = "llama3.1:8b"
    messages: list[ChatMessage] = Field(..., min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    stream: bool = False
    # Pass-through fields (accepted but not used yet)
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None

    @model_validator(mode="after")
    def _require_user_message(self) -> ChatCompletionRequest:
        """At least one message with role 'user' must be present."""
        if not any(m.role == "user" for m in self.messages):
            msg = "At least one message with role 'user' is required"
            raise ValueError(msg)
        return self


# ── Response (non-streaming) ────────────────────────────────────────

class ChatChoice(BaseModel):
    """A single completion choice."""

    index: int
    message: ChatMessage
    finish_reason: str | None = "stop"


class Usage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: Usage | None = None


# ── Response (streaming chunks) ─────────────────────────────────────

class ChatCompletionChunkDelta(BaseModel):
    """Delta content within a streaming chunk."""

    role: str | None = None
    content: str | None = None


class ChatCompletionChunkChoice(BaseModel):
    """A single choice within a streaming chunk."""

    index: int
    delta: ChatCompletionChunkDelta
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    """OpenAI-compatible streaming chunk."""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice]


# ── Error ────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    """Structured error detail matching OpenAI format."""

    message: str
    type: str
    code: str


class ErrorResponse(BaseModel):
    """OpenAI-compatible error response wrapper."""

    error: ErrorDetail
