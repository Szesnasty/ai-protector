"""Risk classification and protection-level recommendation for agents."""

from __future__ import annotations

from src.wizard.models import Agent, ProtectionLevel, RiskLevel


def compute_risk_level(agent: Agent) -> RiskLevel:
    """Deterministically compute risk level from agent capability flags.

    Rules (evaluated top-down, first match wins):
        CRITICAL: has_write_actions AND touches_pii AND is_public_facing
        HIGH:     (has_write_actions AND is_public_facing)
                  OR touches_pii
                  OR handles_secrets
        MEDIUM:   has_write_actions
                  OR (is_public_facing AND has_tools)
        LOW:      everything else
    """
    if agent.has_write_actions and agent.touches_pii and agent.is_public_facing:
        return RiskLevel.CRITICAL

    if (agent.has_write_actions and agent.is_public_facing) or agent.touches_pii or agent.handles_secrets:
        return RiskLevel.HIGH

    if agent.has_write_actions or (agent.is_public_facing and agent.has_tools):
        return RiskLevel.MEDIUM

    return RiskLevel.LOW


def recommend_protection_level(risk_level: RiskLevel) -> ProtectionLevel:
    """Recommend protection level based on risk classification.

    LOW      → proxy_only
    MEDIUM   → agent_runtime
    HIGH     → full
    CRITICAL → full
    """
    match risk_level:
        case RiskLevel.LOW:
            return ProtectionLevel.PROXY_ONLY
        case RiskLevel.MEDIUM:
            return ProtectionLevel.AGENT_RUNTIME
        case RiskLevel.HIGH | RiskLevel.CRITICAL:
            return ProtectionLevel.FULL


def apply_risk_classification(agent: Agent) -> Agent:
    """Compute and set risk_level + protection_level on agent in-place."""
    agent.risk_level = compute_risk_level(agent)
    agent.protection_level = recommend_protection_level(agent.risk_level)
    return agent
