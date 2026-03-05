"""IntentNode — keyword-based intent classifier for the agent."""

from __future__ import annotations

import structlog

from src.agent.state import AgentState
from src.agent.trace.accumulator import TraceAccumulator

logger = structlog.get_logger()

# ── Intent patterns ──────────────────────────────────────

GREETING_PATTERNS = [
    "hello", " hi ", "hi!", "hey", "good morning", "good afternoon", "good evening",
    "howdy", "greetings", "what's up", "hola",
]

ORDER_PATTERNS = [
    "order", "ord-", "tracking", "shipment", "delivery", "where is my",
    "order status", "shipped", "delivered", "package",
]

KB_PATTERNS = [
    "return", "refund", "shipping", "payment", "warranty", "contact",
    "account", "product", "discount", "coupon", "privacy", "support",
    "policy", "how do", "how to", "what is", "tell me about", "info",
    "faq", "help",
]

ADMIN_PATTERNS = [
    "secret", "internal", "api key", "credentials", "config",
    "database", "admin", "confidential", "restricted",
]


def classify_intent(message: str) -> tuple[str, float]:
    """Classify user message into an intent category.

    Returns (intent, confidence).
    """
    text = f" {message.lower().strip()} "

    # Check patterns in priority order
    scores: dict[str, int] = {
        "greeting": 0,
        "order_query": 0,
        "knowledge_search": 0,
        "admin_action": 0,
    }

    for pattern in GREETING_PATTERNS:
        if pattern in text:
            scores["greeting"] += 1

    for pattern in ORDER_PATTERNS:
        if pattern in text:
            scores["order_query"] += 1

    for pattern in KB_PATTERNS:
        if pattern in text:
            scores["knowledge_search"] += 1

    for pattern in ADMIN_PATTERNS:
        if pattern in text:
            scores["admin_action"] += 1

    # Find the best match
    best_intent = max(scores, key=scores.get)  # type: ignore[arg-type]
    best_score = scores[best_intent]

    if best_score == 0:
        return "unknown", 0.0

    total = sum(scores.values())
    confidence = best_score / total if total > 0 else 0.0
    return best_intent, round(confidence, 2)


def intent_node(state: AgentState) -> AgentState:
    """Classify the user's message intent."""
    message = state.get("message", "")
    intent, confidence = classify_intent(message)

    # Trace (spec 07)
    trace = TraceAccumulator(state.get("trace"))
    trace.record_intent(intent, confidence)

    logger.info("intent_node", intent=intent, confidence=confidence, message_preview=message[:80])

    return {
        **state,
        "intent": intent,
        "intent_confidence": confidence,
        "trace": trace.data,
    }
