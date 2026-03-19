"""Tests for DecisionNode with scanner results (step 07c)."""

from __future__ import annotations

import pytest

from src.pipeline.nodes.decision import calculate_risk_score, decision_node
from src.pipeline.state import PipelineState

# ── calculate_risk_score with scanner weights ────────────────────────


class TestScannerWeights:
    """Verify updated scanner weights in risk score calculation."""

    def test_prompt_injection_weighted(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"promptinjection": 0.9},
        }  # type: ignore[typeddict-item]
        # 0.9 * 0.5 (default injection_weight) = 0.45
        assert calculate_risk_score(state) == pytest.approx(0.45)

    def test_toxicity_weighted(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"toxicity": 0.8},
        }  # type: ignore[typeddict-item]
        # 0.8 * 0.5 = 0.4
        assert calculate_risk_score(state) == 0.4

    def test_secrets_flag(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"secrets": 0.95},
        }  # type: ignore[typeddict-item]
        assert calculate_risk_score(state) == 0.6

    def test_invisible_text_flag(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"invisibletext": 1.0},
        }  # type: ignore[typeddict-item]
        assert calculate_risk_score(state) == 0.4

    def test_pii_count_scoring(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"pii": ["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON"], "pii_count": 3},
        }  # type: ignore[typeddict-item]
        # 3 * 0.1 = 0.3
        assert calculate_risk_score(state) == pytest.approx(0.3)

    def test_pii_count_capped(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"pii_count": 10},
        }  # type: ignore[typeddict-item]
        # 10 * 0.1 = 1.0, capped at 0.5
        assert calculate_risk_score(state) == 0.5

    def test_injection_plus_toxicity(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"promptinjection": 0.9, "toxicity": 0.8},
        }  # type: ignore[typeddict-item]
        # 0.9*0.5 + 0.8*0.5 = 0.45 + 0.40 = 0.85
        assert calculate_risk_score(state) == pytest.approx(0.85)


# ── decision_node with PII actions ──────────────────────────────────


class TestDecisionWithPII:
    """PII action logic in decision_node."""

    async def test_pii_block_policy(self) -> None:
        """PII + pii_action=block → BLOCK."""
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"pii": ["EMAIL_ADDRESS"], "pii_count": 1},
            "policy_config": {"thresholds": {"max_risk": 0.7}},
            "scanner_results": {
                "presidio": {"entities": [{"entity_type": "EMAIL_ADDRESS"}], "pii_action": "block"},
            },
        }  # type: ignore[typeddict-item]
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"
        assert "PII detected" in result["blocked_reason"]

    async def test_pii_mask_policy(self) -> None:
        """PII + pii_action=mask → MODIFY."""
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"pii": ["PHONE_NUMBER"], "pii_count": 1},
            "policy_config": {"thresholds": {"max_risk": 0.7}},
            "scanner_results": {
                "presidio": {"entities": [{"entity_type": "PHONE_NUMBER"}], "pii_action": "mask"},
            },
        }  # type: ignore[typeddict-item]
        result = await decision_node(state)
        assert result["decision"] == "MODIFY"

    async def test_pii_flag_allow(self) -> None:
        """PII + pii_action=flag (default) → ALLOW when risk low."""
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"pii": ["EMAIL_ADDRESS"], "pii_count": 1},
            "policy_config": {"thresholds": {"max_risk": 0.7}},
            "scanner_results": {
                "presidio": {"entities": [{"entity_type": "EMAIL_ADDRESS"}], "pii_action": "flag"},
            },
        }  # type: ignore[typeddict-item]
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"

    async def test_injection_balanced_block(self) -> None:
        """Injection + balanced → BLOCK (risk > threshold)."""
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"promptinjection": 0.92},
            "policy_config": {"thresholds": {"max_risk": 0.4}},
            "scanner_results": {},
        }  # type: ignore[typeddict-item]
        # 0.92 * 0.5 (default injection_weight) = 0.46 > 0.4
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"

    async def test_toxic_above_threshold(self) -> None:
        """Toxic prompt above threshold → BLOCK."""
        state: PipelineState = {
            "intent": "jailbreak",
            "risk_flags": {"toxicity": 0.9},
            "policy_config": {"thresholds": {"max_risk": 0.7}},
            "scanner_results": {},
        }  # type: ignore[typeddict-item]
        # 0.6 (jailbreak) + 0.9*0.5=0.45 = 1.05 → capped 1.0 > 0.7
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"

    async def test_clean_all_scanners_allow(self) -> None:
        """Clean prompt + all scanners pass → ALLOW."""
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {},
            "policy_config": {"thresholds": {"max_risk": 0.7}},
            "scanner_results": {
                "llm_guard": {"PromptInjection": {"is_valid": True}},
                "presidio": {"entities": [], "pii_action": "flag"},
            },
        }  # type: ignore[typeddict-item]
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"

    async def test_denylist_overrides_pii_mask(self) -> None:
        """Denylist hit still blocks even if PII action is mask."""
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"denylist_hit": True, "pii": ["EMAIL_ADDRESS"], "pii_count": 1},
            "policy_config": {"thresholds": {"max_risk": 0.7}},
            "scanner_results": {
                "presidio": {"entities": [{"entity_type": "EMAIL_ADDRESS"}], "pii_action": "mask"},
            },
        }  # type: ignore[typeddict-item]
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"
        assert result["blocked_reason"] == "Denylist match"
