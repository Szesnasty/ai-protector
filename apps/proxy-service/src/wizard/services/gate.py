"""Gate evaluation service (spec 31b).

Gates evaluate security checks but behaviour depends on the agent's rollout mode:

  OBSERVE  — always ALLOW, trace original decision with enforced=false
  WARN     — always ALLOW, trace + add warning text
  ENFORCE  — apply original decision (DENY / BLOCK / REDACT)
"""

from __future__ import annotations

from src.wizard.models import (
    GateAction,
    GateDecision,
    GateDecisionType,
    RolloutMode,
)

# ── Simulated gate checks ────────────────────────────────────────────
# Real scanners live in src/security/; these stubs let the wizard
# evaluate rollout-mode logic without touching the real pipeline.

_GATE_DENY_ACTIONS: dict[GateDecisionType, GateAction] = {
    GateDecisionType.RBAC: GateAction.DENY,
    GateDecisionType.INJECTION: GateAction.BLOCK,
    GateDecisionType.PII: GateAction.REDACT,
    GateDecisionType.BUDGET: GateAction.DENY,
}


def evaluate_gate(
    *,
    gate_type: GateDecisionType,
    raw_decision: GateAction,
    rollout_mode: RolloutMode,
    agent_id,
    context: dict | None = None,
) -> GateDecision:
    """Evaluate a gate check respecting rollout mode.

    Returns an **unsaved** GateDecision ORM instance — caller decides
    whether to persist it.
    """
    if rollout_mode == RolloutMode.ENFORCE:
        effective = raw_decision
        enforced = True
        warning = None
    elif rollout_mode == RolloutMode.WARN:
        effective = GateAction.ALLOW
        enforced = False
        warning = _build_warning(gate_type, raw_decision)
    else:  # OBSERVE
        effective = GateAction.ALLOW
        enforced = False
        warning = None

    return GateDecision(
        agent_id=agent_id,
        gate_type=gate_type,
        decision=raw_decision,
        effective_action=effective,
        rollout_mode=rollout_mode,
        enforced=enforced,
        warning=warning,
        context=context,
    )


def _build_warning(gate_type: GateDecisionType, decision: GateAction) -> str:
    """Build a human-readable warning for WARN mode."""
    return f"[AI-Protector] {gate_type.value} gate would have returned {decision.value} in enforce mode"
