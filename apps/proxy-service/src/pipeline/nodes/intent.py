"""IntentNode — keyword-based intent classifier."""

from __future__ import annotations

from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState

# ── Pattern lists (case-insensitive — caller must .lower() the text) ──

JAILBREAK_PATTERNS = [
    "ignore previous",
    "ignore all prior",
    "ignore your instructions",
    "you are now",
    "pretend you are",
    "act as dan",
    "jailbreak",
    "bypass your",
    "override your",
]

EXTRACTION_PATTERNS = [
    "repeat your instructions",
    "system prompt",
    "what are your rules",
    "initial prompt",
    "show your instructions",
    "print your system",
]

CODE_PATTERNS = [
    "write a function",
    "write code",
    "implement",
    "debug",
    "```",
    "programming",
    "refactor",
    "algorithm",
]

TOOL_PATTERNS = [
    "check order",
    "search for",
    "lookup",
    "find me",
    "get status",
]

GREETING_PATTERNS = [
    "hello",
    "hi ",
    "hey ",
    "how are you",
    "thanks",
    "bye",
    "good morning",
]


def classify_intent(text: str) -> tuple[str, float]:
    """Classify text into an intent category using keyword heuristics.

    Returns ``(intent, confidence)`` tuple.
    """
    if any(p in text for p in JAILBREAK_PATTERNS):
        return "jailbreak", 0.8
    if any(p in text for p in EXTRACTION_PATTERNS):
        return "system_prompt_extract", 0.7
    if any(p in text for p in CODE_PATTERNS):
        return "code_gen", 0.6
    if any(p in text for p in TOOL_PATTERNS):
        return "tool_call", 0.5
    if any(p in text for p in GREETING_PATTERNS):
        return "chitchat", 0.9
    return "qa", 0.5


@timed_node("intent")
async def intent_node(state: PipelineState) -> PipelineState:
    """Classify user intent and flag suspicious intents in risk_flags."""
    text = state.get("user_message", "").lower()
    intent, confidence = classify_intent(text)

    risk_flags = {**state.get("risk_flags", {})}
    if intent in ("jailbreak", "system_prompt_extract"):
        risk_flags["suspicious_intent"] = confidence

    return {
        **state,
        "intent": intent,
        "intent_confidence": confidence,
        "risk_flags": risk_flags,
    }
