"""PipelineState — single source of truth flowing through all pipeline nodes."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class PipelineState(TypedDict, total=False):
    """Shared state dict passed through every pipeline node.

    All keys are optional (``total=False``) so nodes only need to set
    the fields they are responsible for.  ParseNode initialises the
    accumulator fields so downstream nodes can safely read them.
    """

    # ── Input (set by ParseNode) ──────────────────────────────────────
    request_id: str  # UUID, same as x-correlation-id
    client_id: str | None
    policy_name: str  # "fast" | "balanced" | "strict" | "paranoid"
    policy_config: dict  # Full policy config JSONB from DB
    model: str
    messages: list[dict]  # Full conversation
    user_message: str  # Extracted last user message
    prompt_hash: str  # SHA-256 of user_message
    temperature: float
    max_tokens: int | None
    stream: bool

    # ── Analysis (accumulated by nodes) ───────────────────────────────
    intent: str | None  # "qa" | "code_gen" | "tool_call" | "chitchat" | …
    intent_confidence: float  # 0.0–1.0
    risk_flags: dict[str, Any]  # {"injection": 0.8, "pii": ["EMAIL"], …}
    risk_score: float  # Aggregated 0.0–1.0
    rules_matched: list[str]  # ["denylist:bomb", "length_exceeded"]
    scanner_results: dict[str, Any]  # Results from LLM Guard, Presidio (Step 07)

    # ── Decision ──────────────────────────────────────────────────────
    decision: Literal["ALLOW", "MODIFY", "BLOCK"] | None
    blocked_reason: str | None
    modified_messages: list[dict] | None

    # ── Output (set after LLM call) ──────────────────────────────────
    llm_response: dict | None
    response_masked: bool
    tokens_in: int | None
    tokens_out: int | None
    latency_ms: int | None

    # ── Output filtering (set by OutputFilterNode) ────────────────────
    output_filtered: bool  # True if output was modified
    output_filter_results: dict  # {"pii_redacted": N, "secrets_redacted": N, "system_leak": bool}
    sanitized_messages: list[dict] | None  # Conversation with PII/secrets stripped

    # ── Metadata ──────────────────────────────────────────────────────
    node_timings: dict[str, float]  # {"parse": 1.2, "intent": 45.3} (ms)
    errors: list[str]  # Non-fatal errors from nodes
