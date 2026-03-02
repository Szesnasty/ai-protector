"""Tests for PipelineState, timed_node decorator, and parse_node."""

from __future__ import annotations

import asyncio
import hashlib

from src.pipeline.nodes import timed_node
from src.pipeline.nodes.parse import parse_node
from src.pipeline.state import PipelineState

# ── PipelineState ──────────────────────────────────────────────────────


class TestPipelineState:
    """PipelineState is a TypedDict — verify it accepts the documented fields."""

    def test_empty_state_allowed(self) -> None:
        """total=False means an empty dict is valid."""
        state: PipelineState = {}  # type: ignore[typeddict-item]
        assert isinstance(state, dict)

    def test_full_state_round_trip(self) -> None:
        state: PipelineState = {
            "request_id": "abc-123",
            "client_id": "client-1",
            "policy_name": "balanced",
            "policy_config": {"max_tokens": 4096},
            "model": "llama3",
            "messages": [{"role": "user", "content": "hi"}],
            "user_message": "hi",
            "prompt_hash": hashlib.sha256(b"hi").hexdigest(),
            "temperature": 0.7,
            "max_tokens": 4096,
            "stream": False,
            "intent": "qa",
            "intent_confidence": 0.9,
            "risk_flags": {},
            "risk_score": 0.0,
            "rules_matched": [],
            "scanner_results": {},
            "decision": "ALLOW",
            "blocked_reason": None,
            "modified_messages": None,
            "llm_response": None,
            "response_masked": False,
            "tokens_in": 10,
            "tokens_out": 20,
            "latency_ms": 150,
            "node_timings": {"parse": 0.5},
            "errors": [],
        }
        assert state["decision"] == "ALLOW"
        assert state["prompt_hash"] == hashlib.sha256(b"hi").hexdigest()


# ── timed_node decorator ──────────────────────────────────────────────


class TestTimedNode:
    async def test_records_timing(self) -> None:
        @timed_node("test_node")
        async def dummy(state: PipelineState) -> PipelineState:
            await asyncio.sleep(0.01)  # ~10ms
            return {**state}

        result = await dummy({})  # type: ignore[typeddict-item]
        assert "test_node" in result["node_timings"]
        assert result["node_timings"]["test_node"] >= 5  # at least 5ms

    async def test_preserves_existing_timings(self) -> None:
        @timed_node("second")
        async def dummy(state: PipelineState) -> PipelineState:
            return {**state, "node_timings": {"first": 1.0}}

        result = await dummy({})  # type: ignore[typeddict-item]
        assert result["node_timings"]["first"] == 1.0
        assert "second" in result["node_timings"]

    async def test_preserves_function_name(self) -> None:
        @timed_node("named")
        async def my_node(state: PipelineState) -> PipelineState:
            return {**state}

        assert my_node.__name__ == "my_node"


# ── parse_node ─────────────────────────────────────────────────────────


class TestParseNode:
    async def test_extracts_last_user_message(self) -> None:
        state: PipelineState = {
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "first question"},
                {"role": "assistant", "content": "first answer"},
                {"role": "user", "content": "second question"},
            ],
        }  # type: ignore[typeddict-item]

        result = await parse_node(state)
        assert result["user_message"] == "second question"

    async def test_computes_sha256_hash(self) -> None:
        state: PipelineState = {
            "messages": [{"role": "user", "content": "hello world"}],
        }  # type: ignore[typeddict-item]

        result = await parse_node(state)
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert result["prompt_hash"] == expected
        assert len(result["prompt_hash"]) == 64  # SHA-256 hex

    async def test_initialises_accumulator_fields(self) -> None:
        state: PipelineState = {
            "messages": [{"role": "user", "content": "test"}],
        }  # type: ignore[typeddict-item]

        result = await parse_node(state)
        assert result["risk_flags"] == {}
        assert result["risk_score"] == 0.0
        assert result["rules_matched"] == []
        assert result["scanner_results"] == {}
        assert result["decision"] is None
        assert result["blocked_reason"] is None
        assert result["modified_messages"] is None
        assert result["errors"] == []
        assert result["response_masked"] is False

    async def test_no_user_message_sets_empty_string(self) -> None:
        state: PipelineState = {
            "messages": [{"role": "system", "content": "You are helpful."}],
        }  # type: ignore[typeddict-item]

        result = await parse_node(state)
        assert result["user_message"] == ""
        assert result["prompt_hash"] == hashlib.sha256(b"").hexdigest()

    async def test_no_user_message_adds_error(self) -> None:
        state: PipelineState = {
            "messages": [{"role": "assistant", "content": "hi"}],
        }  # type: ignore[typeddict-item]

        result = await parse_node(state)
        assert len(result["errors"]) == 1
        assert "no user message" in result["errors"][0]

    async def test_empty_messages_list(self) -> None:
        state: PipelineState = {"messages": []}  # type: ignore[typeddict-item]

        result = await parse_node(state)
        assert result["user_message"] == ""
        assert "no user message" in result["errors"][0]

    async def test_missing_messages_key(self) -> None:
        state: PipelineState = {}  # type: ignore[typeddict-item]

        result = await parse_node(state)
        assert result["user_message"] == ""
        assert "no user message" in result["errors"][0]

    async def test_preserves_existing_state_fields(self) -> None:
        state: PipelineState = {
            "request_id": "req-123",
            "client_id": "client-A",
            "model": "llama3",
            "messages": [{"role": "user", "content": "hi"}],
        }  # type: ignore[typeddict-item]

        result = await parse_node(state)
        assert result["request_id"] == "req-123"
        assert result["client_id"] == "client-A"
        assert result["model"] == "llama3"

    async def test_node_timing_recorded(self) -> None:
        state: PipelineState = {
            "messages": [{"role": "user", "content": "hi"}],
        }  # type: ignore[typeddict-item]

        result = await parse_node(state)
        assert "parse" in result["node_timings"]
        assert isinstance(result["node_timings"]["parse"], float)
        assert result["node_timings"]["parse"] >= 0
