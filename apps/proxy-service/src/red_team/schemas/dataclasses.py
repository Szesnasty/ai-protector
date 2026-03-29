"""Pure dataclasses for inter-module contracts.

These are NOT Pydantic models — they are simple data containers
used for function signatures between modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A single tool/function invocation extracted from a target response."""

    name: str
    arguments: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RawTargetResponse:
    """Canonical representation of what the target returned.

    Produced by the Response Normalizer, consumed by Evaluators.
    """

    body_text: str  # Extracted text content (always present, may be "")
    parsed_json: dict | None  # Parsed JSON body, or None
    tool_calls: list[ToolCall] | None  # Extracted tool calls, or None
    status_code: int  # HTTP status code
    latency_ms: float  # Round-trip time in milliseconds
    raw_body: str  # Original response body (for debugging)
    provider_format: str  # "openai" | "anthropic" | "generic_json" | "plain_text"


@dataclass(frozen=True, slots=True)
class EvalResult:
    """Result of evaluating a single scenario against a target response."""

    passed: bool  # True = target resisted the attack
    confidence: float  # 1.0 for deterministic, <1.0 for heuristic
    detail: str  # Human-readable explanation
    detector_type: str  # Which detector produced this result
    matched_evidence: str | None = None  # Specific string/pattern/tool that matched
