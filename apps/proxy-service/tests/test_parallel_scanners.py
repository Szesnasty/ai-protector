"""Tests for parallel scanner wrapper node."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.pipeline.nodes.scanners import parallel_scanners_node


def _base_state(
    *,
    nodes: list[str] | None = None,
    risk_flags: dict | None = None,
    scanner_results: dict | None = None,
) -> dict:
    """Minimal pipeline state for parallel_scanners_node."""
    return {
        "request_id": "test-1",
        "user_message": "Hello, how are you?",
        "messages": [{"role": "user", "content": "Hello, how are you?"}],
        "policy_config": {"nodes": nodes or [], "thresholds": {}},
        "risk_flags": risk_flags or {},
        "scanner_results": scanner_results or {},
        "errors": [],
    }


# ── Parallel execution ───────────────────────────────────────────────


class TestParallelExecution:
    """Both scanners run concurrently."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.scanners.presidio_node", new_callable=AsyncMock)
    @patch("src.pipeline.nodes.scanners.llm_guard_node", new_callable=AsyncMock)
    async def test_both_scanners_run(self, mock_llm_guard, mock_presidio):
        mock_llm_guard.return_value = {
            "risk_flags": {"promptinjection": 0.9},
            "scanner_results": {"llm_guard": {"PromptInjection": {"is_valid": False, "score": 0.9}}},
            "errors": [],
        }
        mock_presidio.return_value = {
            "risk_flags": {"pii": ["EMAIL_ADDRESS"], "pii_count": 1},
            "scanner_results": {"presidio": {"entities": [{"entity_type": "EMAIL_ADDRESS"}], "pii_action": "flag"}},
            "errors": [],
        }

        state = _base_state(nodes=["llm_guard", "presidio"])
        result = await parallel_scanners_node(state)

        mock_llm_guard.assert_awaited_once()
        mock_presidio.assert_awaited_once()
        assert result["risk_flags"]["promptinjection"] == 0.9
        assert result["risk_flags"]["pii"] == ["EMAIL_ADDRESS"]
        assert "llm_guard" in result["scanner_results"]
        assert "presidio" in result["scanner_results"]

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.scanners.presidio_node", new_callable=AsyncMock)
    @patch("src.pipeline.nodes.scanners.llm_guard_node", new_callable=AsyncMock)
    async def test_records_timing(self, mock_llm_guard, mock_presidio):
        mock_llm_guard.return_value = {"risk_flags": {}, "scanner_results": {}, "errors": []}
        mock_presidio.return_value = {"risk_flags": {}, "scanner_results": {}, "errors": []}

        state = _base_state(nodes=["llm_guard", "presidio"])
        result = await parallel_scanners_node(state)
        assert "scanners" in result.get("node_timings", {})


# ── Policy-driven selection ───────────────────────────────────────────


class TestPolicySelection:
    """Scanner selection driven by policy config."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.scanners.presidio_node", new_callable=AsyncMock)
    @patch("src.pipeline.nodes.scanners.llm_guard_node", new_callable=AsyncMock)
    async def test_fast_policy_no_scanners(self, mock_llm_guard, mock_presidio):
        state = _base_state(nodes=[])
        result = await parallel_scanners_node(state)

        mock_llm_guard.assert_not_awaited()
        mock_presidio.assert_not_awaited()
        assert result["risk_flags"] == {}

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.scanners.presidio_node", new_callable=AsyncMock)
    @patch("src.pipeline.nodes.scanners.llm_guard_node", new_callable=AsyncMock)
    async def test_balanced_only_llm_guard(self, mock_llm_guard, mock_presidio):
        mock_llm_guard.return_value = {
            "risk_flags": {},
            "scanner_results": {"llm_guard": {}},
            "errors": [],
        }

        state = _base_state(nodes=["llm_guard"])
        result = await parallel_scanners_node(state)

        mock_llm_guard.assert_awaited_once()
        mock_presidio.assert_not_awaited()
        assert "llm_guard" in result["scanner_results"]

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.scanners.presidio_node", new_callable=AsyncMock)
    @patch("src.pipeline.nodes.scanners.llm_guard_node", new_callable=AsyncMock)
    async def test_no_nodes_key_skips(self, mock_llm_guard, mock_presidio):
        """Missing 'nodes' key in policy_config → no scanners."""
        state = _base_state()
        state["policy_config"] = {"thresholds": {}}
        await parallel_scanners_node(state)

        mock_llm_guard.assert_not_awaited()
        mock_presidio.assert_not_awaited()


# ── Error handling ────────────────────────────────────────────────────


class TestScannerErrors:
    """One scanner fails, other succeeds → merged results correct."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.scanners.presidio_node", new_callable=AsyncMock)
    @patch("src.pipeline.nodes.scanners.llm_guard_node", new_callable=AsyncMock)
    async def test_one_fails_other_succeeds(self, mock_llm_guard, mock_presidio):
        mock_llm_guard.side_effect = RuntimeError("model load failed")
        mock_presidio.return_value = {
            "risk_flags": {"pii": ["EMAIL_ADDRESS"], "pii_count": 1},
            "scanner_results": {"presidio": {"entities": []}},
            "errors": [],
        }

        state = _base_state(nodes=["llm_guard", "presidio"])
        result = await parallel_scanners_node(state)

        # Presidio results still present
        assert result["risk_flags"]["pii"] == ["EMAIL_ADDRESS"]
        assert "presidio" in result["scanner_results"]
        # LLM Guard error recorded
        assert any("llm_guard" in e for e in result["errors"])

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.scanners.presidio_node", new_callable=AsyncMock)
    @patch("src.pipeline.nodes.scanners.llm_guard_node", new_callable=AsyncMock)
    async def test_both_fail_gracefully(self, mock_llm_guard, mock_presidio):
        mock_llm_guard.side_effect = RuntimeError("fail")
        mock_presidio.side_effect = RuntimeError("fail")

        state = _base_state(nodes=["llm_guard", "presidio"])
        result = await parallel_scanners_node(state)

        assert result["risk_flags"] == {}
        assert len(result["errors"]) == 2


# ── Merging ───────────────────────────────────────────────────────────


class TestMerging:
    """Results from multiple scanners are properly merged."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.scanners.llm_guard_node", new_callable=AsyncMock)
    async def test_preserves_existing_flags(self, mock_llm_guard):
        mock_llm_guard.return_value = {
            "risk_flags": {"promptinjection": 0.8},
            "scanner_results": {"llm_guard": {}},
            "errors": [],
        }

        state = _base_state(
            nodes=["llm_guard"],
            risk_flags={"denylist_hit": True},
        )
        result = await parallel_scanners_node(state)

        assert result["risk_flags"]["denylist_hit"] is True
        assert result["risk_flags"]["promptinjection"] == 0.8

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.scanners.presidio_node", new_callable=AsyncMock)
    @patch("src.pipeline.nodes.scanners.llm_guard_node", new_callable=AsyncMock)
    async def test_merges_errors_from_both(self, mock_llm_guard, mock_presidio):
        mock_llm_guard.return_value = {
            "risk_flags": {},
            "scanner_results": {},
            "errors": ["llm_guard.Toxicity: timeout after 30s"],
        }
        mock_presidio.return_value = {
            "risk_flags": {},
            "scanner_results": {},
            "errors": ["presidio: spacy error"],
        }

        state = _base_state(nodes=["llm_guard", "presidio"])
        result = await parallel_scanners_node(state)

        assert len(result["errors"]) == 2

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.scanners.presidio_node", new_callable=AsyncMock)
    async def test_modified_messages_propagated(self, mock_presidio):
        mock_presidio.return_value = {
            "risk_flags": {"pii": ["EMAIL_ADDRESS"], "pii_count": 1},
            "scanner_results": {"presidio": {"entities": [], "pii_action": "mask"}},
            "errors": [],
            "modified_messages": [{"role": "user", "content": "My email is <EMAIL_ADDRESS>"}],
        }

        state = _base_state(nodes=["presidio"])
        result = await parallel_scanners_node(state)

        assert result["modified_messages"][0]["content"] == "My email is <EMAIL_ADDRESS>"
