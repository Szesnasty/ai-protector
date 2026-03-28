"""Pydantic models for request/response contracts and internal data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


# ── Request models ──


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str


class RequestMetadata(BaseModel):
    scenario_id: str | None = None
    target_variant: str | None = None


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    messages: list[ChatMessage]
    stream: bool = False
    response_mode: str = "text"  # "text" | "json"
    use_retrieval: bool | None = None
    use_tools: bool | None = None
    metadata: RequestMetadata | None = None


# ── Response models ──


class TraceRef(BaseModel):
    request_id: str
    streamed: bool
    used_retrieval: bool
    used_tools: bool


class ChatResponse(BaseModel):
    id: str
    conversation_id: str
    variant: str
    model: str
    output_text: str
    structured_output: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    system_canary_enabled: bool
    trace: TraceRef
    blocked: bool = Field(default=False, exclude=True)
    proxy_block_headers: dict[str, str] = Field(default_factory=dict, exclude=True)


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "reference-chat-target"
    mode: str
    model: str
    streaming_enabled: bool
    retrieval_enabled: bool
    tools_enabled: bool
    structured_output_enabled: bool
    canary_enabled: bool


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


# ── Structured output schema ──


class StructuredAnswer(BaseModel):
    answer: str
    requires_follow_up: bool
    risk_flags: list[str] = Field(default_factory=list)


# ── Internal data models ──


class Conversation(BaseModel):
    conversation_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: Any = None


class TraceRecord(BaseModel):
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    app_mode: str
    conversation_id: str
    scenario_id: str | None = None
    retrieval_used: bool = False
    retrieval_docs: list[str] = Field(default_factory=list)
    tools_enabled: bool = False
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    response_mode: str = "text"
    canary_id: str | None = None
    canary_token: str | None = None
    response_length: int = 0
    structured_output_valid: bool | None = None
    structured_output_error: str | None = None
    streamed: bool = False
    model: str = ""
    error_type: str | None = None
    error_message: str | None = None


# ── Model backend internal result ──


class BackendResult(BaseModel):
    text: str = ""
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    model: str = ""
    blocked: bool = False
    proxy_block_headers: dict[str, str] = Field(default_factory=dict)
