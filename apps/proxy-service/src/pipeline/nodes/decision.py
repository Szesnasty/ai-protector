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
    invisible_weight = thresholds.get("invisible_weight", 0.8)
    pii_per_entity = thresholds.get("pii_per_entity_weight", 0.1)
    pii_max = thresholds.get("pii_max_weight", 0.5)

    # Intent-based
    intent = state.get("intent")
    if intent == "jailbreak":
        score += 0.6
    elif intent == "system_prompt_extract":
        score += 0.4
    elif intent == "role_bypass":
        score += 0.5
    elif intent == "tool_abuse":
        score += 0.4
    elif intent == "agent_exfiltration":
        score += 0.5
    elif intent == "social_engineering":
        score += 0.3
    elif intent == "harmful_content":
        score += 0.6
    elif intent == "misinformation":
        score += 0.5
    elif intent == "resource_exhaustion":
        score += 0.4
    elif intent == "supply_chain" or intent == "rag_poisoning" or intent == "pii_request":
        score += 0.5
    elif intent == "confused_deputy":
        score += 0.4
    elif intent == "template_injection":
        score += 0.6
    elif intent == "virtual_context":
        score += 0.4
    elif intent == "crescendo":
        score += 0.5

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

    # NeMo Guardrails signals
    if flags.get("nemo_blocked"):
        nemo_score = max(
            (
                v
                for k, v in flags.items()
                if k.startswith("nemo_") and k != "nemo_blocked" and isinstance(v, (int, float))
            ),
            default=0.0,
        )
        score += float(nemo_score) * thresholds.get("nemo_weight", 0.7)

    # Custom rule score_boost (accumulated from rules_node)
    score += flags.get("score_boost", 0.0)

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
    if risk_score >= max_risk:
        return {
            **state,
            "decision": "BLOCK",
            "blocked_reason": f"Risk {risk_score:.2f} > threshold {max_risk}",
            "risk_score": risk_score,
        }

    # PII mask → force MODIFY
    if pii_action == "mask" and has_pii:
        return {**state, "decision": "MODIFY", "risk_score": risk_score}

    # Suspicious intent detected → BLOCK (attack pattern identified)
    if state.get("risk_flags", {}).get("suspicious_intent"):
        return {
            **state,
            "decision": "BLOCK",
            "blocked_reason": f"Suspicious intent detected (risk {risk_score:.2f})",
            "risk_score": risk_score,
        }

    # Secrets detected → BLOCK (API keys, tokens, connection strings etc.)
    if state.get("risk_flags", {}).get("secrets"):
        return {
            **state,
            "decision": "BLOCK",
            "blocked_reason": "Secrets detected in input",
            "risk_score": risk_score,
        }

    # NeMo rail triggered — contribute via risk_score, NOT hard-block.
    # The nemo_blocked signal is already incorporated into calculate_risk_score()
    # via the weighted formula (nemo_score * nemo_weight). Hard-blocking here
    # caused false positives on benign queries like "search products laptop"
    # because NeMo embeddings matched attack intents at low similarity thresholds.
    # If NeMo + other signals push risk_score >= max_risk, the threshold check
    # above already handles the block correctly.

    return {**state, "decision": "ALLOW", "risk_score": risk_score}
