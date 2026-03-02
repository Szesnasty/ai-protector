"""Tests for DecisionNode, TransformNode, LLMCallNode, graph routing (step 06c)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline.graph import route_after_decision
from src.pipeline.nodes.decision import calculate_risk_score, decision_node
from src.pipeline.nodes.llm_call import llm_call_node
from src.pipeline.nodes.transform import SAFETY_PREFIX, transform_node
from src.pipeline.state import PipelineState

# ── calculate_risk_score ─────────────────────────────────────────────


class TestCalculateRiskScore:
    def test_clean_prompt_zero(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {},
        }  # type: ignore[typeddict-item]
        assert calculate_risk_score(state) == 0.0

    def test_jailbreak_intent(self) -> None:
        state: PipelineState = {
            "intent": "jailbreak",
            "risk_flags": {},
        }  # type: ignore[typeddict-item]
        assert calculate_risk_score(state) == 0.6

    def test_extraction_intent(self) -> None:
        state: PipelineState = {
            "intent": "system_prompt_extract",
            "risk_flags": {},
        }  # type: ignore[typeddict-item]
        assert calculate_risk_score(state) == 0.4

    def test_denylist_hit(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"denylist_hit": True},
        }  # type: ignore[typeddict-item]
        assert calculate_risk_score(state) == 0.8

    def test_multiple_flags_additive(self) -> None:
        state: PipelineState = {
            "intent": "jailbreak",
            "risk_flags": {"denylist_hit": True, "encoded_content": True},
        }  # type: ignore[typeddict-item]
        # 0.6 + 0.8 + 0.3 = 1.7 → capped at 1.0
        assert calculate_risk_score(state) == 1.0

    def test_capped_at_one(self) -> None:
        state: PipelineState = {
            "intent": "jailbreak",
            "risk_flags": {
                "denylist_hit": True,
                "encoded_content": True,
                "special_chars": True,
                "length_exceeded": 20000,
            },
        }  # type: ignore[typeddict-item]
        assert calculate_risk_score(state) == 1.0

    def test_scanner_injection_flag(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"promptinjection": 0.9},
        }  # type: ignore[typeddict-item]
        assert calculate_risk_score(state) == pytest.approx(0.72)

    def test_pii_flag(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"pii": ["EMAIL"], "pii_count": 1},
        }  # type: ignore[typeddict-item]
        assert calculate_risk_score(state) == 0.1


# ── decision_node ────────────────────────────────────────────────────


class TestDecisionNode:
    async def test_allow_clean_prompt(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {},
            "policy_config": {"thresholds": {"max_risk": 0.7}},
        }  # type: ignore[typeddict-item]
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"
        assert result["risk_score"] == 0.0

    async def test_block_denylist(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {"denylist_hit": True},
            "policy_config": {"thresholds": {"max_risk": 0.7}},
        }  # type: ignore[typeddict-item]
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"
        assert result["blocked_reason"] == "Denylist match"

    async def test_block_high_risk(self) -> None:
        state: PipelineState = {
            "intent": "jailbreak",
            "risk_flags": {"encoded_content": True},
            "policy_config": {"thresholds": {"max_risk": 0.7}},
        }  # type: ignore[typeddict-item]
        # risk = 0.6 + 0.3 = 0.9 > 0.7
        result = await decision_node(state)
        assert result["decision"] == "BLOCK"
        assert "Risk" in result["blocked_reason"]

    async def test_modify_suspicious_intent(self) -> None:
        state: PipelineState = {
            "intent": "system_prompt_extract",
            "risk_flags": {"suspicious_intent": 0.7},
            "policy_config": {"thresholds": {"max_risk": 0.7}},
        }  # type: ignore[typeddict-item]
        # risk = 0.4 ≤ 0.7, but suspicious_intent flag → MODIFY
        result = await decision_node(state)
        assert result["decision"] == "MODIFY"

    async def test_default_threshold(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {},
            "policy_config": {},
        }  # type: ignore[typeddict-item]
        result = await decision_node(state)
        assert result["decision"] == "ALLOW"

    async def test_records_timing(self) -> None:
        state: PipelineState = {
            "intent": "qa",
            "risk_flags": {},
            "policy_config": {},
        }  # type: ignore[typeddict-item]
        result = await decision_node(state)
        assert "decision" in result["node_timings"]


# ── transform_node ───────────────────────────────────────────────────


class TestTransformNode:
    async def test_skip_when_allow(self) -> None:
        state: PipelineState = {
            "decision": "ALLOW",
            "messages": [{"role": "user", "content": "hi"}],
        }  # type: ignore[typeddict-item]
        result = await transform_node(state)
        assert "modified_messages" not in result or result.get("modified_messages") is None

    async def test_inject_safety_no_system(self) -> None:
        state: PipelineState = {
            "decision": "MODIFY",
            "risk_flags": {"suspicious_intent": 0.7},
            "messages": [{"role": "user", "content": "hello"}],
        }  # type: ignore[typeddict-item]
        result = await transform_node(state)
        msgs = result["modified_messages"]
        assert msgs[0]["role"] == "system"
        assert "IMPORTANT: You are a helpful assistant" in msgs[0]["content"]

    async def test_inject_safety_existing_system(self) -> None:
        state: PipelineState = {
            "decision": "MODIFY",
            "risk_flags": {"suspicious_intent": 0.7},
            "messages": [
                {"role": "system", "content": "You are a bot."},
                {"role": "user", "content": "hello"},
            ],
        }  # type: ignore[typeddict-item]
        result = await transform_node(state)
        msgs = result["modified_messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"].startswith(SAFETY_PREFIX)
        assert "You are a bot." in msgs[0]["content"]

    async def test_spotlighting_delimiters(self) -> None:
        state: PipelineState = {
            "decision": "MODIFY",
            "risk_flags": {"suspicious_intent": 0.7},
            "messages": [{"role": "user", "content": "test input"}],
        }  # type: ignore[typeddict-item]
        result = await transform_node(state)
        user_msg = next(m for m in result["modified_messages"] if m["role"] == "user")
        assert user_msg["content"].startswith("[USER_INPUT_START]")
        assert user_msg["content"].endswith("[USER_INPUT_END]")

    async def test_does_not_mutate_original(self) -> None:
        original = [{"role": "user", "content": "hi"}]
        state: PipelineState = {
            "decision": "MODIFY",
            "risk_flags": {"suspicious_intent": 0.7},
            "messages": original,
        }  # type: ignore[typeddict-item]
        await transform_node(state)
        assert original[0]["content"] == "hi"  # unchanged

    async def test_records_timing(self) -> None:
        state: PipelineState = {
            "decision": "MODIFY",
            "risk_flags": {"suspicious_intent": 0.7},
            "messages": [{"role": "user", "content": "hi"}],
        }  # type: ignore[typeddict-item]
        result = await transform_node(state)
        assert "transform" in result["node_timings"]


# ── llm_call_node ────────────────────────────────────────────────────


class TestLLMCallNode:
    @patch("src.pipeline.nodes.llm_call.llm_completion", new_callable=AsyncMock)
    async def test_calls_llm_with_original_messages(self, mock_llm: AsyncMock) -> None:
        usage = MagicMock(prompt_tokens=10, completion_tokens=20)
        mock_llm.return_value = MagicMock(usage=usage)
        state: PipelineState = {
            "model": "llama3",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.7,
            "max_tokens": 100,
        }  # type: ignore[typeddict-item]
        result = await llm_call_node(state)
        mock_llm.assert_awaited_once()
        assert result["tokens_in"] == 10
        assert result["tokens_out"] == 20
        assert result["llm_response"] is not None

    @patch("src.pipeline.nodes.llm_call.llm_completion", new_callable=AsyncMock)
    async def test_uses_modified_messages(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = MagicMock(usage=None)
        modified = [{"role": "system", "content": "safe"}, {"role": "user", "content": "hi"}]
        state: PipelineState = {
            "model": "llama3",
            "messages": [{"role": "user", "content": "hi"}],
            "modified_messages": modified,
            "temperature": 0.5,
            "max_tokens": None,
        }  # type: ignore[typeddict-item]
        await llm_call_node(state)
        call_args = mock_llm.call_args
        assert call_args.kwargs["messages"] == modified

    @patch("src.pipeline.nodes.llm_call.llm_completion", new_callable=AsyncMock)
    async def test_no_usage(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = MagicMock(usage=None)
        state: PipelineState = {
            "model": "llama3",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.7,
        }  # type: ignore[typeddict-item]
        result = await llm_call_node(state)
        assert result["tokens_in"] is None
        assert result["tokens_out"] is None

    @patch("src.pipeline.nodes.llm_call.llm_completion", new_callable=AsyncMock)
    async def test_records_timing(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = MagicMock(usage=None)
        state: PipelineState = {
            "model": "llama3",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.7,
        }  # type: ignore[typeddict-item]
        result = await llm_call_node(state)
        assert "llm_call" in result["node_timings"]


# ── route_after_decision ─────────────────────────────────────────────


class TestRouteAfterDecision:
    def test_block(self) -> None:
        assert route_after_decision({"decision": "BLOCK"}) == "block"  # type: ignore[typeddict-item]

    def test_modify(self) -> None:
        assert route_after_decision({"decision": "MODIFY"}) == "modify"  # type: ignore[typeddict-item]

    def test_allow(self) -> None:
        assert route_after_decision({"decision": "ALLOW"}) == "allow"  # type: ignore[typeddict-item]

    def test_default_allow(self) -> None:
        assert route_after_decision({}) == "allow"  # type: ignore[typeddict-item]
