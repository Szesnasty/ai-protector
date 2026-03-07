"""Tests for policy-aware DecisionNode (step 08c).

Covers:
  - 4 seeded policy levels (fast, balanced, strict, paranoid)
  - Custom weight overrides
  - Default thresholds fallback
  - Configurable scanner weights in calculate_risk_score
"""

from __future__ import annotations

import pytest

from src.pipeline.nodes.decision import calculate_risk_score, decision_node
from src.pipeline.state import PipelineState

# ── Helpers ──────────────────────────────────────────────────────────

# Seed-matching policy configs (mirrors src/db/seed.py)
FAST_CONFIG: dict = {
    "thresholds": {"max_risk": 0.9},
}
BALANCED_CONFIG: dict = {
    "thresholds": {"max_risk": 0.7, "injection_threshold": 0.5},
}
STRICT_CONFIG: dict = {
    "thresholds": {"max_risk": 0.5, "injection_threshold": 0.3, "pii_action": "mask"},
}
PARANOID_CONFIG: dict = {
    "thresholds": {
        "max_risk": 0.3,
        "injection_threshold": 0.2,
        "pii_action": "block",
        "enable_canary": True,
    },
}


def _make_state(
    *,
    intent: str = "qa",
    risk_flags: dict | None = None,
    policy_config: dict | None = None,
    scanner_results: dict | None = None,
) -> PipelineState:
    s: dict = {
        "intent": intent,
        "risk_flags": risk_flags or {},
        "policy_config": policy_config or {},
    }
    if scanner_results is not None:
        s["scanner_results"] = scanner_results
    return s  # type: ignore[return-value]


# ── Fast policy tests ────────────────────────────────────────────────


class TestFastPolicy:
    """Fast policy: max_risk=0.9, no scanners."""

    async def test_clean_prompt_allow(self) -> None:
        state = _make_state(policy_config=FAST_CONFIG)
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"

    async def test_jailbreak_intent_allow(self) -> None:
        """Jailbreak intent alone scores 0.6 < 0.9 → ALLOW."""
        state = _make_state(intent="jailbreak", policy_config=FAST_CONFIG)
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"
        assert result["risk_score"] == pytest.approx(0.6)

    async def test_encoded_plus_jailbreak_allow(self) -> None:
        """0.6 + 0.3 = 0.9, equal to max_risk → ALLOW (> not >=)."""
        state = _make_state(
            intent="jailbreak",
            risk_flags={"encoded_content": True},
            policy_config=FAST_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"

    async def test_denylist_still_blocks(self) -> None:
        """Denylist is a hard block regardless of policy."""
        state = _make_state(
            risk_flags={"denylist_hit": True},
            policy_config=FAST_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"
        assert result["blocked_reason"] == "Denylist match"

    async def test_extreme_risk_blocks(self) -> None:
        """Jailbreak + denylist + encoded = 1.7→1.0 > 0.9 → BLOCK (via denylist hard-block)."""
        state = _make_state(
            intent="jailbreak",
            risk_flags={"denylist_hit": True, "encoded_content": True},
            policy_config=FAST_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"


# ── Balanced policy tests ────────────────────────────────────────────


class TestBalancedPolicy:
    """Balanced policy: max_risk=0.7, LLM Guard scanners."""

    async def test_clean_prompt_allow(self) -> None:
        state = _make_state(policy_config=BALANCED_CONFIG)
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"

    async def test_injection_above_threshold_block(self) -> None:
        """Injection 0.92 * 0.8 = 0.736 > 0.7 → BLOCK."""
        state = _make_state(
            risk_flags={"promptinjection": 0.92},
            policy_config=BALANCED_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"

    async def test_injection_below_threshold_allow(self) -> None:
        """Injection 0.5 * 0.8 = 0.4 < 0.7 → ALLOW."""
        state = _make_state(
            risk_flags={"promptinjection": 0.5},
            policy_config=BALANCED_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"

    async def test_pii_flagged_allow(self) -> None:
        """Balanced has pii_action=flag (default), PII stays ALLOW if risk ok."""
        state = _make_state(
            risk_flags={"pii": ["EMAIL_ADDRESS"], "pii_count": 1},
            policy_config=BALANCED_CONFIG,
            scanner_results={"presidio": {"entities": [{"entity_type": "EMAIL_ADDRESS"}], "pii_action": "flag"}},
        )
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"

    async def test_jailbreak_blocks(self) -> None:
        """Jailbreak 0.6 + encoded 0.3 = 0.9 > 0.7 → BLOCK."""
        state = _make_state(
            intent="jailbreak",
            risk_flags={"encoded_content": True},
            policy_config=BALANCED_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"


# ── Strict policy tests ─────────────────────────────────────────────


class TestStrictPolicy:
    """Strict policy: max_risk=0.5, pii_action=mask."""

    async def test_clean_prompt_allow(self) -> None:
        state = _make_state(policy_config=STRICT_CONFIG)
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"

    async def test_extraction_intent_allow(self) -> None:
        """extraction 0.4 < 0.5 → ALLOW (but if suspicious_intent → MODIFY)."""
        state = _make_state(intent="system_prompt_extract", policy_config=STRICT_CONFIG)
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"

    async def test_jailbreak_blocks(self) -> None:
        """Jailbreak 0.6 > 0.5 → BLOCK."""
        state = _make_state(intent="jailbreak", policy_config=STRICT_CONFIG)
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"

    async def test_pii_mask_modify(self) -> None:
        """PII + pii_action=mask → MODIFY."""
        state = _make_state(
            risk_flags={"pii": ["EMAIL_ADDRESS"], "pii_count": 1},
            policy_config=STRICT_CONFIG,
            scanner_results={"presidio": {"entities": [{"entity_type": "EMAIL_ADDRESS"}], "pii_action": "mask"}},
        )
        result = await decision_node(state)
        assert result["decision"] == "MODIFY"

    async def test_injection_moderate_blocks(self) -> None:
        """Injection 0.7 * 0.8 = 0.56 > 0.5 → BLOCK."""
        state = _make_state(
            risk_flags={"promptinjection": 0.7},
            policy_config=STRICT_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"

    async def test_toxicity_moderate_allow(self) -> None:
        """Toxicity 0.8 * 0.5 = 0.4 < 0.5 → ALLOW."""
        state = _make_state(
            risk_flags={"toxicity": 0.8},
            policy_config=STRICT_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"


# ── Paranoid policy tests ────────────────────────────────────────────


class TestParanoidPolicy:
    """Paranoid policy: max_risk=0.3, pii_action=block."""

    async def test_clean_prompt_allow(self) -> None:
        state = _make_state(policy_config=PARANOID_CONFIG)
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"

    async def test_pii_block(self) -> None:
        """PII + pii_action=block → BLOCK."""
        state = _make_state(
            risk_flags={"pii": ["PHONE_NUMBER"], "pii_count": 1},
            policy_config=PARANOID_CONFIG,
            scanner_results={"presidio": {"entities": [{"entity_type": "PHONE_NUMBER"}], "pii_action": "block"}},
        )
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"
        assert "PII detected" in result["blocked_reason"]

    async def test_extraction_intent_blocks(self) -> None:
        """extraction 0.4 > 0.3 → BLOCK."""
        state = _make_state(intent="system_prompt_extract", policy_config=PARANOID_CONFIG)
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"

    async def test_jailbreak_blocks(self) -> None:
        """jailbreak 0.6 > 0.3 → BLOCK."""
        state = _make_state(intent="jailbreak", policy_config=PARANOID_CONFIG)
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"

    async def test_any_injection_blocks(self) -> None:
        """Even small injection 0.4 * 0.8 = 0.32 > 0.3 → BLOCK."""
        state = _make_state(
            risk_flags={"promptinjection": 0.4},
            policy_config=PARANOID_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"

    async def test_encoded_content_blocks(self) -> None:
        """encoded 0.3 + special_chars 0.1 = 0.4 > 0.3 → BLOCK."""
        state = _make_state(
            risk_flags={"encoded_content": True, "special_chars": True},
            policy_config=PARANOID_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"

    async def test_low_toxicity_blocks(self) -> None:
        """Toxicity 0.7 * 0.5 = 0.35 > 0.3 → BLOCK."""
        state = _make_state(
            risk_flags={"toxicity": 0.7},
            policy_config=PARANOID_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"


# ── Custom weight overrides ──────────────────────────────────────────


class TestCustomWeights:
    """Verify custom weight overrides in policy thresholds."""

    def test_high_injection_weight(self) -> None:
        """injection_weight=1.0 makes small injection score higher."""
        state = _make_state(
            risk_flags={"promptinjection": 0.5},
            policy_config={"thresholds": {"injection_weight": 1.0}},
        )
        # 0.5 * 1.0 = 0.5
        assert calculate_risk_score(state) == pytest.approx(0.5)

    def test_zero_injection_weight(self) -> None:
        """injection_weight=0.0 ignores injection signals."""
        state = _make_state(
            risk_flags={"promptinjection": 0.9},
            policy_config={"thresholds": {"injection_weight": 0.0}},
        )
        assert calculate_risk_score(state) == 0.0

    def test_custom_toxicity_weight(self) -> None:
        state = _make_state(
            risk_flags={"toxicity": 0.8},
            policy_config={"thresholds": {"toxicity_weight": 0.9}},
        )
        # 0.8 * 0.9 = 0.72
        assert calculate_risk_score(state) == pytest.approx(0.72)

    def test_custom_secrets_weight(self) -> None:
        state = _make_state(
            risk_flags={"secrets": 1.0},
            policy_config={"thresholds": {"secrets_weight": 0.3}},
        )
        assert calculate_risk_score(state) == pytest.approx(0.3)

    def test_custom_invisible_weight(self) -> None:
        state = _make_state(
            risk_flags={"invisibletext": 1.0},
            policy_config={"thresholds": {"invisible_weight": 0.2}},
        )
        assert calculate_risk_score(state) == pytest.approx(0.2)

    def test_custom_pii_weights(self) -> None:
        state = _make_state(
            risk_flags={"pii_count": 3},
            policy_config={"thresholds": {"pii_per_entity_weight": 0.2, "pii_max_weight": 0.4}},
        )
        # 3 * 0.2 = 0.6, capped at 0.4
        assert calculate_risk_score(state) == pytest.approx(0.4)

    def test_custom_pii_no_cap(self) -> None:
        state = _make_state(
            risk_flags={"pii_count": 2},
            policy_config={"thresholds": {"pii_per_entity_weight": 0.15, "pii_max_weight": 1.0}},
        )
        # 2 * 0.15 = 0.3
        assert calculate_risk_score(state) == pytest.approx(0.3)

    async def test_custom_weight_changes_decision(self) -> None:
        """High injection_weight can flip ALLOW→BLOCK."""
        # Default weight 0.8: 0.6 * 0.8 = 0.48 < 0.5 → ALLOW
        state_default = _make_state(
            risk_flags={"promptinjection": 0.6},
            policy_config={"thresholds": {"max_risk": 0.5}},
        )
        result = await decision_node(state_default)
        assert result["decision"] == "ALLOW"

        # Custom weight 1.0: 0.6 * 1.0 = 0.6 > 0.5 → BLOCK
        state_custom = _make_state(
            risk_flags={"promptinjection": 0.6},
            policy_config={"thresholds": {"max_risk": 0.5, "injection_weight": 1.0}},
        )
        result = await decision_node(state_custom)
        assert result["decision"] == "BLOCK"


# ── Default thresholds fallback ──────────────────────────────────────


class TestDefaultThresholds:
    """Missing or empty policy_config yields sensible defaults."""

    def test_no_policy_config(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"promptinjection": 0.9},
        }  # type: ignore[typeddict-item]
        # Default injection_weight=0.8 → 0.9 * 0.8 = 0.72
        assert calculate_risk_score(state) == pytest.approx(0.72)

    def test_empty_policy_config(self) -> None:
        state = _make_state(
            risk_flags={"promptinjection": 0.9},
            policy_config={},
        )
        assert calculate_risk_score(state) == pytest.approx(0.72)

    def test_empty_thresholds(self) -> None:
        state = _make_state(
            risk_flags={"toxicity": 0.8},
            policy_config={"thresholds": {}},
        )
        # Default toxicity_weight=0.5 → 0.8 * 0.5 = 0.4
        assert calculate_risk_score(state) == pytest.approx(0.4)

    async def test_default_max_risk_0_7(self) -> None:
        """Missing max_risk defaults to 0.7."""
        # risk 0.6 (jailbreak) < 0.7 → ALLOW
        state = _make_state(intent="jailbreak", policy_config={})
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"

    async def test_default_max_risk_blocks_high(self) -> None:
        """risk > 0.7 → BLOCK with default config."""
        state = _make_state(
            intent="jailbreak",
            risk_flags={"encoded_content": True},
            policy_config={},
        )
        # 0.6 + 0.3 = 0.9 > 0.7
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"


# ── Cross-policy comparison ──────────────────────────────────────────


class TestCrossPolicyComparison:
    """Same input, different policies → different decisions."""

    async def test_injection_fast_vs_paranoid(self) -> None:
        """Moderate injection: ALLOW on fast, BLOCK on paranoid."""
        flags = {"promptinjection": 0.6}
        # fast: 0.6*0.8=0.48 < 0.9 → ALLOW
        result_fast = await decision_node(_make_state(risk_flags=flags, policy_config=FAST_CONFIG))
        assert result_fast["decision"] == "ALLOW"
        # paranoid: 0.6*0.8=0.48 > 0.3 → BLOCK
        result_paranoid = await decision_node(_make_state(risk_flags=flags, policy_config=PARANOID_CONFIG))
        assert result_paranoid["decision"] == "BLOCK"

    async def test_pii_strict_vs_paranoid(self) -> None:
        """PII: MODIFY on strict (mask), BLOCK on paranoid (block)."""
        flags = {"pii": ["EMAIL_ADDRESS"], "pii_count": 1}
        scanners_mask = {"presidio": {"entities": [{"entity_type": "EMAIL_ADDRESS"}], "pii_action": "mask"}}
        scanners_block = {"presidio": {"entities": [{"entity_type": "EMAIL_ADDRESS"}], "pii_action": "block"}}

        result_strict = await decision_node(
            _make_state(risk_flags=flags, policy_config=STRICT_CONFIG, scanner_results=scanners_mask)
        )
        assert result_strict["decision"] == "MODIFY"

        result_paranoid = await decision_node(
            _make_state(risk_flags=flags, policy_config=PARANOID_CONFIG, scanner_results=scanners_block)
        )
        assert result_paranoid["decision"] == "BLOCK"

    async def test_jailbreak_fast_allows_balanced_blocks(self) -> None:
        """Jailbreak+encoded: ALLOW on fast (0.9 threshold), BLOCK on balanced (0.7)."""
        flags = {"encoded_content": True}
        # 0.6 + 0.3 = 0.9
        result_fast = await decision_node(_make_state(intent="jailbreak", risk_flags=flags, policy_config=FAST_CONFIG))
        assert result_fast["decision"] == "ALLOW"

        result_balanced = await decision_node(
            _make_state(intent="jailbreak", risk_flags=flags, policy_config=BALANCED_CONFIG)
        )
        assert result_balanced["decision"] == "BLOCK"


# ── Agent intent weights (Step 22c) ─────────────────────────────────


class TestAgentIntentWeights:
    """Agent-specific intents contribute to risk score."""

    async def test_role_bypass_score(self) -> None:
        """role_bypass adds 0.5 to risk score."""
        state = _make_state(intent="role_bypass", policy_config=BALANCED_CONFIG)
        score = calculate_risk_score(state)
        assert score == pytest.approx(0.5)

    async def test_tool_abuse_score(self) -> None:
        """tool_abuse adds 0.4."""
        state = _make_state(intent="tool_abuse", policy_config=BALANCED_CONFIG)
        score = calculate_risk_score(state)
        assert score == pytest.approx(0.4)

    async def test_exfiltration_score(self) -> None:
        """agent_exfiltration adds 0.5."""
        state = _make_state(intent="agent_exfiltration", policy_config=BALANCED_CONFIG)
        score = calculate_risk_score(state)
        assert score == pytest.approx(0.5)

    async def test_social_engineering_score(self) -> None:
        """social_engineering adds 0.3."""
        state = _make_state(intent="social_engineering", policy_config=BALANCED_CONFIG)
        score = calculate_risk_score(state)
        assert score == pytest.approx(0.3)

    async def test_role_bypass_blocks_balanced(self) -> None:
        """role_bypass (0.5) + encoded (0.3) = 0.8 > 0.7 → BLOCK."""
        state = _make_state(
            intent="role_bypass",
            risk_flags={"encoded_content": True},
            policy_config=BALANCED_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"


# ── NeMo Guardrails weight (Step 22d) ───────────────────────────────


class TestNemoGuardrailsWeight:
    """NeMo blocked signal contributes to risk score."""

    async def test_nemo_blocked_adds_weight(self) -> None:
        """nemo_blocked + nemo_role_bypass 0.85 → 0.85 * 0.7 = 0.595."""
        state = _make_state(
            risk_flags={"nemo_blocked": True, "nemo_role_bypass": 0.85},
            policy_config=BALANCED_CONFIG,
        )
        score = calculate_risk_score(state)
        assert score == pytest.approx(0.85 * 0.7)

    async def test_nemo_blocked_with_intent_blocks(self) -> None:
        """role_bypass(0.5) + nemo(0.85*0.7=0.595) = 1.0(capped) > 0.7 → BLOCK."""
        state = _make_state(
            intent="role_bypass",
            risk_flags={"nemo_blocked": True, "nemo_role_bypass": 0.85},
            policy_config=BALANCED_CONFIG,
        )
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"
        assert result["risk_score"] == pytest.approx(1.0)

    async def test_nemo_custom_weight(self) -> None:
        """Custom nemo_weight=0.9 → nemo_role_bypass 0.85 * 0.9 = 0.765."""
        config = {"thresholds": {"max_risk": 0.7, "nemo_weight": 0.9}}
        state = _make_state(
            risk_flags={"nemo_blocked": True, "nemo_role_bypass": 0.85},
            policy_config=config,
        )
        score = calculate_risk_score(state)
        assert score == pytest.approx(0.85 * 0.9)

    async def test_no_nemo_flag_no_weight(self) -> None:
        """Without nemo_blocked flag, NeMo weight not applied."""
        state = _make_state(
            risk_flags={"nemo_role_bypass": 0.85},
            policy_config=BALANCED_CONFIG,
        )
        score = calculate_risk_score(state)
        assert score == pytest.approx(0.0)  # nemo_blocked not set
