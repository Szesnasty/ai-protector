"""AgentState — shared state flowing through all agent graph nodes."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class ToolCallRecord(TypedDict):
    """A single tool invocation record."""

    tool: str
    args: dict[str, Any]
    result: str
    allowed: bool


class CheckResult(TypedDict):
    """Result of a single security check in the pre-tool gate."""

    check: str  # "rbac", "scope", "schema", "context_risk", "limits", "confirmation"
    passed: bool
    detail: str | None


class GateDecision(TypedDict):
    """Pre-tool gate decision for a single proposed tool call."""

    tool: str
    args: dict[str, Any]
    decision: str  # "ALLOW", "BLOCK", "MODIFY", "REQUIRE_CONFIRMATION"
    reason: str | None
    checks: list[CheckResult]
    modified_args: dict[str, Any] | None  # Only if MODIFY
    risk_score: float  # 0.0–1.0 for this specific tool call


class AgentState(TypedDict, total=False):
    """Shared state dict passed through every agent graph node."""

    # ── Input ──────────────────────────────────────────────
    session_id: str
    user_role: str  # "customer" | "admin"
    message: str  # Current user message
    chat_history: list[dict[str, str]]  # Previous conversation turns
    policy: str  # Policy name for proxy
    model: str  # LLM model to use
    api_key: str | None  # External provider API key (from browser)

    # ── Analysis ───────────────────────────────────────────
    intent: str  # greeting, order_query, knowledge_search, admin_action, unknown
    intent_confidence: float
    allowed_tools: list[str]  # Tools available for this role

    # ── Tool execution ─────────────────────────────────────
    tool_calls: list[ToolCallRecord]
    tool_plan: list[dict[str, Any]]  # Tools the LLM wants to call next
    iterations: int  # ReAct loop count

    # ── Pre-tool Gate ──────────────────────────────────────
    gate_decisions: list[GateDecision]  # Per-tool gate outcomes
    pending_confirmation: dict[str, Any] | None  # Tool awaiting user approval

    # ── LLM ────────────────────────────────────────────────
    llm_messages: list[dict[str, str]]  # Messages sent to LLM
    llm_response: str  # Raw LLM response text

    # ── Firewall ───────────────────────────────────────────
    firewall_decision: dict[str, Any]

    # ── Output ─────────────────────────────────────────────
    final_response: str

    # ── Metadata ───────────────────────────────────────────
    errors: list[str]
    node_timings: dict[str, float]
