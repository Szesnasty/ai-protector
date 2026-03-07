"""Tests for logging pipeline node — Postgres + Langfuse trace."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline.nodes.logging_node import (
    _build_tags,
    _safe_response_preview,
    _scanner_summary,
    logging_node,
)

# ── Helpers ───────────────────────────────────────────────────────────


def _base_state(
    *,
    decision: str = "ALLOW",
    blocked_reason: str | None = None,
    response_content: str | None = "Hello!",
    policy: str = "balanced",
    intent: str | None = "qa",
    risk_score: float = 0.1,
    scanner_results: dict | None = None,
    output_filter_results: dict | None = None,
    output_filtered: bool = False,
) -> dict:
    llm_response = None
    if response_content is not None:
        llm_response = {
            "choices": [{"message": {"role": "assistant", "content": response_content}}],
            "model": "llama3.1:8b",
        }
    return {
        "request_id": "test-log-1",
        "client_id": "client-1",
        "policy_name": policy,
        "policy_config": {"nodes": ["output_filter", "memory_hygiene", "logging"], "thresholds": {}},
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "test"}],
        "user_message": "test",
        "prompt_hash": "abc123",
        "decision": decision,
        "blocked_reason": blocked_reason,
        "intent": intent,
        "risk_flags": {},
        "risk_score": risk_score,
        "scanner_results": scanner_results or {},
        "output_filter_results": output_filter_results or {},
        "output_filtered": output_filtered,
        "llm_response": llm_response,
        "response_masked": decision == "MODIFY",
        "latency_ms": 100,
        "tokens_in": 10,
        "tokens_out": 20,
        "node_timings": {"parse": 1.0, "intent": 2.0, "decision": 0.5},
        "errors": [],
    }


# ── Test 1: ALLOW state → Postgres row created ───────────────────────


class TestAllowPath:
    """ALLOW state logs to Postgres and Langfuse."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.logging_node.create_trace", new_callable=AsyncMock, return_value=None)
    @patch("src.pipeline.nodes.logging_node.log_request_from_state", new_callable=AsyncMock)
    async def test_allow_logged(self, mock_log, mock_trace):
        state = _base_state(decision="ALLOW")
        result = await logging_node(state)

        mock_log.assert_called_once()
        logged_state = mock_log.call_args[0][0]
        assert logged_state["decision"] == "ALLOW"
        assert result["decision"] == "ALLOW"  # State content preserved


# ── Test 2: BLOCK state → Postgres row created ───────────────────────


class TestBlockPath:
    """BLOCK state logs with blocked_reason."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.logging_node.create_trace", new_callable=AsyncMock, return_value=None)
    @patch("src.pipeline.nodes.logging_node.log_request_from_state", new_callable=AsyncMock)
    async def test_block_logged(self, mock_log, mock_trace):
        state = _base_state(decision="BLOCK", blocked_reason="injection detected", response_content=None)
        await logging_node(state)

        mock_log.assert_called_once()
        logged = mock_log.call_args[0][0]
        assert logged["decision"] == "BLOCK"
        assert logged["blocked_reason"] == "injection detected"


# ── Test 3: MODIFY state → Postgres row created ──────────────────────


class TestModifyPath:
    """MODIFY state logs with response_masked=True."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.logging_node.create_trace", new_callable=AsyncMock, return_value=None)
    @patch("src.pipeline.nodes.logging_node.log_request_from_state", new_callable=AsyncMock)
    async def test_modify_logged(self, mock_log, mock_trace):
        state = _base_state(decision="MODIFY")
        await logging_node(state)

        logged = mock_log.call_args[0][0]
        assert logged["response_masked"] is True


# ── Test 4: Scanner results saved ─────────────────────────────────────


class TestScannerResults:
    """Scanner results are passed to the logger."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.logging_node.create_trace", new_callable=AsyncMock, return_value=None)
    @patch("src.pipeline.nodes.logging_node.log_request_from_state", new_callable=AsyncMock)
    async def test_scanner_results_logged(self, mock_log, mock_trace):
        state = _base_state(scanner_results={"llm_guard": {"is_valid": True, "score": 0.9}})
        await logging_node(state)

        logged = mock_log.call_args[0][0]
        assert logged["scanner_results"]["llm_guard"]["score"] == 0.9


# ── Test 5: Output filter results saved ───────────────────────────────


class TestOutputFilterResults:
    """Output filter results are passed to the logger."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.logging_node.create_trace", new_callable=AsyncMock, return_value=None)
    @patch("src.pipeline.nodes.logging_node.log_request_from_state", new_callable=AsyncMock)
    async def test_output_filter_results_logged(self, mock_log, mock_trace):
        state = _base_state(output_filter_results={"pii_redacted": 2, "secrets_redacted": 1, "system_leak": False})
        await logging_node(state)

        logged = mock_log.call_args[0][0]
        assert logged["output_filter_results"]["pii_redacted"] == 2


# ── Test 6: Node timings saved ────────────────────────────────────────


class TestNodeTimings:
    """Node timings are passed to the logger."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.logging_node.create_trace", new_callable=AsyncMock, return_value=None)
    @patch("src.pipeline.nodes.logging_node.log_request_from_state", new_callable=AsyncMock)
    async def test_timings_logged(self, mock_log, mock_trace):
        state = _base_state()
        await logging_node(state)

        logged = mock_log.call_args[0][0]
        assert "parse" in logged["node_timings"]


# ── Test 7: Logging failure → swallowed ───────────────────────────────


class TestLoggingFailure:
    """Postgres failure is swallowed — state is still returned."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.logging_node.create_trace", new_callable=AsyncMock, return_value=None)
    @patch(
        "src.pipeline.nodes.logging_node.log_request_from_state",
        new_callable=AsyncMock,
        side_effect=Exception("db down"),
    )
    async def test_failure_swallowed(self, mock_log, mock_trace):
        state = _base_state()
        result = await logging_node(state)

        # No exception raised, state returned
        assert result["decision"] == "ALLOW"


# ── Test 8: Node doesn't modify state ────────────────────────────────


class TestStateUnmodified:
    """logging_node returns the exact same state object."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.logging_node.create_trace", new_callable=AsyncMock, return_value=None)
    @patch("src.pipeline.nodes.logging_node.log_request_from_state", new_callable=AsyncMock)
    async def test_state_identity(self, mock_log, mock_trace):
        state = _base_state()
        result = await logging_node(state)

        # State should be the same (logging doesn't modify)
        assert result["request_id"] == state["request_id"]
        assert result["decision"] == state["decision"]


# ── Langfuse trace integration ────────────────────────────────────────


class TestLangfuseTrace:
    """logging_node creates Langfuse trace with spans."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.logging_node.add_pipeline_spans", new_callable=AsyncMock)
    @patch("src.pipeline.nodes.logging_node.create_trace", new_callable=AsyncMock)
    @patch("src.pipeline.nodes.logging_node.log_request_from_state", new_callable=AsyncMock)
    async def test_trace_created_with_spans(self, mock_log, mock_trace, mock_spans):
        mock_trace_obj = MagicMock()
        mock_trace.return_value = mock_trace_obj

        state = _base_state()
        await logging_node(state)

        mock_trace.assert_called_once()
        call_kwargs = mock_trace.call_args.kwargs
        assert call_kwargs["trace_id"] == "test-log-1"
        assert "decision" in call_kwargs["output_data"]

        mock_spans.assert_called_once_with(mock_trace_obj, state["node_timings"])


# ── Helper function tests ─────────────────────────────────────────────


class TestHelpers:
    """Direct tests for helper functions."""

    def test_safe_response_preview_normal(self):
        state = _base_state(response_content="Hello world!")
        assert _safe_response_preview(state) == "Hello world!"

    def test_safe_response_preview_none(self):
        state = _base_state(response_content=None)
        assert _safe_response_preview(state) is None

    def test_safe_response_preview_truncated(self):
        state = _base_state(response_content="x" * 1000)
        result = _safe_response_preview(state, max_len=100)
        assert len(result) == 100

    def test_scanner_summary(self):
        state = _base_state(
            scanner_results={
                "llm_guard": {"is_valid": True, "score": 0.9, "raw_output": "..."},
                "presidio": {"pii_action": "mask", "entities": [1, 2, 3]},
            }
        )
        summary = _scanner_summary(state)
        assert summary["llm_guard"] == {"is_valid": True, "score": 0.9}
        assert summary["presidio"] == {"pii_action": "mask"}

    def test_build_tags(self):
        state = _base_state(decision="BLOCK", intent="injection", output_filtered=True)
        tags = _build_tags(state)
        assert "decision:BLOCK" in tags
        assert "policy:balanced" in tags
        assert "intent:injection" in tags
        assert "output_filtered" in tags

    def test_build_tags_minimal(self):
        state = _base_state(intent=None, output_filtered=False)
        tags = _build_tags(state)
        assert "decision:ALLOW" in tags
        assert "output_filtered" not in tags


# ── Timing recorded ──────────────────────────────────────────────────


class TestTimingRecorded:
    """The timed_node decorator records execution time."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.logging_node.create_trace", new_callable=AsyncMock, return_value=None)
    @patch("src.pipeline.nodes.logging_node.log_request_from_state", new_callable=AsyncMock)
    async def test_timing_present(self, mock_log, mock_trace):
        state = _base_state()
        result = await logging_node(state)
        assert "logging" in result["node_timings"]
