"""Tests for rules_node with block/flag/score_boost actions (step 14b)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.pipeline.nodes.rules import SEVERITY_SCORE, rules_node
from src.services.denylist import DenylistHit


def _make_hit(
    phrase: str = "test",
    category: str = "general",
    action: str = "block",
    severity: str = "medium",
    is_regex: bool = False,
    description: str = "",
) -> DenylistHit:
    return DenylistHit(
        phrase=phrase,
        category=category,
        action=action,
        severity=severity,
        is_regex=is_regex,
        description=description,
    )


def _state(text: str = "test input", **kwargs) -> dict:
    return {
        "user_message": text,
        "messages": [],
        "policy_name": "balanced",
        "rules_matched": [],
        "risk_flags": {},
        **kwargs,
    }


class TestBlockAction:
    """Block action should set denylist_hit and add to rules_matched."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.rules.check_denylist", new_callable=AsyncMock)
    async def test_block_sets_denylist_hit(self, mock_check):
        mock_check.return_value = [_make_hit(phrase="bad word", action="block")]
        result = await rules_node(_state())
        assert result["risk_flags"]["denylist_hit"] is True
        assert "denylist:bad word" in result["rules_matched"]

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.rules.check_denylist", new_callable=AsyncMock)
    async def test_block_multiple(self, mock_check):
        mock_check.return_value = [
            _make_hit(phrase="p1", action="block"),
            _make_hit(phrase="p2", action="block"),
        ]
        result = await rules_node(_state())
        assert "denylist:p1" in result["rules_matched"]
        assert "denylist:p2" in result["rules_matched"]


class TestFlagAction:
    """Flag action should create custom_flags entries."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.rules.check_denylist", new_callable=AsyncMock)
    async def test_flag_creates_custom_flags(self, mock_check):
        mock_check.return_value = [
            _make_hit(
                phrase="competitor mention",
                category="brand_competitor",
                action="flag",
                severity="low",
                description="Brand mention",
            ),
        ]
        result = await rules_node(_state())
        assert "denylist_hit" not in result["risk_flags"]
        flags = result["risk_flags"]["custom_flags"]
        assert len(flags) == 1
        assert flags[0]["phrase"] == "competitor mention"
        assert flags[0]["category"] == "brand_competitor"
        assert flags[0]["severity"] == "low"
        assert flags[0]["description"] == "Brand mention"


class TestScoreBoostAction:
    """Score boost action should accumulate in risk_flags.score_boost."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.rules.check_denylist", new_callable=AsyncMock)
    async def test_single_score_boost(self, mock_check):
        mock_check.return_value = [
            _make_hit(action="score_boost", severity="high"),
        ]
        result = await rules_node(_state())
        assert result["risk_flags"]["score_boost"] == pytest.approx(0.3)

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.rules.check_denylist", new_callable=AsyncMock)
    async def test_stacking_score_boosts(self, mock_check):
        mock_check.return_value = [
            _make_hit(phrase="p1", action="score_boost", severity="high"),
            _make_hit(phrase="p2", action="score_boost", severity="medium"),
        ]
        result = await rules_node(_state())
        expected = SEVERITY_SCORE["high"] + SEVERITY_SCORE["medium"]
        assert result["risk_flags"]["score_boost"] == pytest.approx(expected)


class TestMixedActions:
    """Mixed actions from different rules should all be processed."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.rules.check_denylist", new_callable=AsyncMock)
    async def test_block_and_flag_and_boost(self, mock_check):
        mock_check.return_value = [
            _make_hit(phrase="block_me", action="block"),
            _make_hit(phrase="flag_me", category="brand", action="flag", severity="low", description="test"),
            _make_hit(phrase="boost_me", action="score_boost", severity="critical"),
        ]
        result = await rules_node(_state())
        assert result["risk_flags"]["denylist_hit"] is True
        assert "denylist:block_me" in result["rules_matched"]
        assert len(result["risk_flags"]["custom_flags"]) == 1
        assert result["risk_flags"]["score_boost"] == pytest.approx(0.5)


class TestNoHits:
    """No denylist hits should not add flags."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.rules.check_denylist", new_callable=AsyncMock)
    async def test_clean_text(self, mock_check):
        mock_check.return_value = []
        result = await rules_node(_state())
        assert "denylist_hit" not in result["risk_flags"]
        assert "custom_flags" not in result["risk_flags"]
        assert "score_boost" not in result["risk_flags"]
