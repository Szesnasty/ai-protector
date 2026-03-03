"""DecisionNode — aggregates risk signals and makes ALLOW / MODIFY / BLOCK decision."""

from __future__ import annotations

from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState


def calculate_risk_score(state: PipelineState) -> float:
    """Weighted aggregation of all risk signals, capped at 1.0."""
    score = 0.0
    flags: dict = state.get("risk_flags", {})
    thresholds: dict = state.get("policy_config", {}).get("thresholds", {})

    # Policy-configurable scanner weights (defaults match legacy values)
    injection_weight = thresholds.get("injection_weight", 0.8)
    toxicity_weight = thresholds.get("toxicity_weight", 0.5)
    secrets_weight = thresholds.get("secrets_weight", 0.6)
    invisible_weight = thresholds.get("invisible_weight", 0.4)
    pii_per_entity = thresholds.get("pii_per_entity_weight", 0.1)
    pii_max = thresholds.get("pii_max_weight", 0.5)

    # Intent-based
    intent = state.get("intent")
    if intent == "jailbreak":
        score += 0.6
    elif intent == "system_prompt_extract":
        score += 0.4

    # Rule-based
    if flags.get("denylist_hit"):
        score += 0.8
    if flags.get("encoded_content"):
        score += 0.3
    if flags.get("special_chars"):
        score += 0.1
    if flags.get("length_exceeded"):
        score += 0.1

    # LLM Guard signals
    if "promptinjection" in flags:
        score += float(flags["promptinjection"]) * injection_weight
    if "toxicity" in flags:
        score += float(flags["toxicity"]) * toxicity_weight
    if "secrets" in flags:
        score += secrets_weight
    if "invisibletext" in flags:
        score += invisible_weight

    # Presidio PII
    pii_count = flags.get("pii_count", 0)
    if pii_count > 0:
        score += min(pii_count * pii_per_entity, pii_max)

    return min(score, 1.0)


@timed_node("decision")
async def decision_node(state: PipelineState) -> PipelineState:
    """Decide whether to ALLOW, MODIFY, or BLOCK the request."""
    policy_config: dict = state.get("policy_config", {})
    thresholds = policy_config.get("thresholds", {})
    max_risk = thresholds.get("max_risk", 0.7)

    risk_score = calculate_risk_score(state)

    # Hard block: denylist match
    if state.get("risk_flags", {}).get("denylist_hit"):
        return {
            **state,
            "decision": "BLOCK",
            "blocked_reason": "Denylist match",
            "risk_score": risk_score,
        }

    # PII action overrides
    presidio = state.get("scanner_results", {}).get("presidio", {})
    pii_action = presidio.get("pii_action", "flag")
    has_pii = bool(state.get("risk_flags", {}).get("pii"))

    if pii_action == "block" and has_pii:
        return {
            **state,
            "decision": "BLOCK",
            "blocked_reason": "PII detected (block policy)",
            "risk_score": risk_score,
        }

    # Risk threshold
    if risk_score > max_risk:
        return {
            **state,
            "decision": "BLOCK",
            "blocked_reason": f"Risk {risk_score:.2f} > threshold {max_risk}",
            "risk_score": risk_score,
        }

    # PII mask → force MODIFY
    if pii_action == "mask" and has_pii:
        return {**state, "decision": "MODIFY", "risk_score": risk_score}

    # Suspicious but below threshold → MODIFY
    if state.get("risk_flags", {}).get("suspicious_intent"):
        return {**state, "decision": "MODIFY", "risk_score": risk_score}

    return {**state, "decision": "ALLOW", "risk_score": risk_score}
