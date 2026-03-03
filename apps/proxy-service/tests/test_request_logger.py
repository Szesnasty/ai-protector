"""Tests for the request logger service."""

from __future__ import annotations

import hashlib
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.services.request_logger import (
    _prompt_hash,
    _prompt_preview,
    log_request,
    log_request_from_state,
)

# ── Helper function tests ───────────────────────────────────────────


class TestPromptHash:
    """Verify SHA-256 hashing of the last user message."""

    def test_returns_sha256_hex(self):
        messages = [
            {"role": "system", "content": "You are a bot."},
            {"role": "user", "content": "Hello world!"},
        ]
        result = _prompt_hash(messages)
        assert result is not None
        assert len(result) == 64  # SHA-256 hex
        assert result == hashlib.sha256(b"Hello world!").hexdigest()

    def test_uses_last_user_message(self):
        messages = [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Reply"},
            {"role": "user", "content": "Second"},
        ]
        result = _prompt_hash(messages)
        assert result == hashlib.sha256(b"Second").hexdigest()

    def test_returns_none_without_user(self):
        messages = [{"role": "system", "content": "Hello"}]
        assert _prompt_hash(messages) is None


class TestPromptPreview:
    """Verify truncation of last user message."""

    def test_short_message(self):
        messages = [{"role": "user", "content": "Hello"}]
        assert _prompt_preview(messages) == "Hello"

    def test_truncates_long_message(self):
        long = "A" * 500
        messages = [{"role": "user", "content": long}]
        result = _prompt_preview(messages)
        assert result is not None
        assert len(result) == 200

    def test_returns_none_without_user(self):
        messages = [{"role": "system", "content": "System only"}]
        assert _prompt_preview(messages) is None


# ── log_request integration ─────────────────────────────────────────


class TestLogRequest:
    """Verify log_request writes to DB and handles failures gracefully."""

    @pytest.mark.asyncio
    @patch("src.services.request_logger._resolve_policy_id", new_callable=AsyncMock)
    @patch("src.services.request_logger.async_session")
    async def test_inserts_request_row(self, mock_session_maker, mock_resolve):
        policy_id = uuid.uuid4()
        mock_resolve.return_value = policy_id

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = mock_session

        await log_request(
            client_id="test-client",
            policy_name="balanced",
            model="llama3.1:8b",
            messages=[{"role": "user", "content": "Hello"}],
            decision="ALLOW",
            latency_ms=150,
            tokens_in=10,
            tokens_out=5,
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        row = mock_session.add.call_args[0][0]
        assert row.client_id == "test-client"
        assert row.policy_id == policy_id
        assert row.decision == "ALLOW"
        assert row.latency_ms == 150
        assert row.tokens_in == 10
        assert row.tokens_out == 5
        assert row.prompt_hash is not None
        assert len(row.prompt_hash) == 64

    @pytest.mark.asyncio
    @patch("src.services.request_logger._resolve_policy_id", new_callable=AsyncMock)
    @patch("src.services.request_logger.async_session")
    async def test_default_client_id(self, mock_session_maker, mock_resolve):
        mock_resolve.return_value = uuid.uuid4()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = mock_session

        await log_request(
            client_id=None,
            policy_name="balanced",
            model="llama3.1:8b",
            messages=[{"role": "user", "content": "Hi"}],
        )

        row = mock_session.add.call_args[0][0]
        assert row.client_id == "anonymous"

    @pytest.mark.asyncio
    @patch("src.services.request_logger._resolve_policy_id", new_callable=AsyncMock)
    async def test_unknown_policy_does_not_raise(self, mock_resolve):
        mock_resolve.return_value = None

        # Should not raise — just logs a warning and returns
        await log_request(
            client_id="test",
            policy_name="nonexistent",
            model="x",
            messages=[{"role": "user", "content": "Hi"}],
        )

    @pytest.mark.asyncio
    @patch("src.services.request_logger._resolve_policy_id", new_callable=AsyncMock)
    @patch("src.services.request_logger.async_session")
    async def test_commit_failure_does_not_raise(self, mock_session_maker, mock_resolve):
        mock_resolve.return_value = uuid.uuid4()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock(side_effect=RuntimeError("DB down"))
        mock_session_maker.return_value = mock_session

        # Should NOT raise — errors are swallowed
        await log_request(
            client_id="test",
            policy_name="balanced",
            model="llama3.1:8b",
            messages=[{"role": "user", "content": "Hi"}],
        )


# ── log_request_from_state ──────────────────────────────────────────


def _sample_state() -> dict:
    """Minimal state dict for log_request_from_state tests."""
    return {
        "request_id": "req-1",
        "client_id": "client-1",
        "policy_name": "balanced",
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "Hi"}],
        "prompt_hash": "abc123",
        "decision": "ALLOW",
        "blocked_reason": None,
        "intent": "qa",
        "risk_flags": {},
        "risk_score": 0.1,
        "latency_ms": 100,
        "tokens_in": 10,
        "tokens_out": 20,
        "response_masked": False,
        "scanner_results": {"llm_guard": {"is_valid": True}},
        "output_filter_results": {"pii_redacted": 0},
        "node_timings": {"parse": 1.0, "intent": 2.0},
    }


class TestLogRequestFromState:
    """Tests for the pipeline-integrated logger."""

    @pytest.mark.asyncio
    @patch("src.services.request_logger._resolve_policy_id", new_callable=AsyncMock)
    @patch("src.services.request_logger.async_session")
    async def test_writes_row(self, mock_session_maker, mock_resolve):
        """log_request_from_state inserts a full row with JSONB columns."""
        policy_id = uuid.uuid4()
        mock_resolve.return_value = policy_id

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = mock_session

        await log_request_from_state(_sample_state())

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        row = mock_session.add.call_args[0][0]
        assert row.policy_id == policy_id
        assert row.decision == "ALLOW"
        assert row.scanner_results == {"llm_guard": {"is_valid": True}}
        assert row.output_filter_results == {"pii_redacted": 0}
        assert row.node_timings == {"parse": 1.0, "intent": 2.0}

    @pytest.mark.asyncio
    @patch("src.services.request_logger._resolve_policy_id", new_callable=AsyncMock)
    @patch("src.services.request_logger.async_session")
    async def test_old_log_request_still_works(self, mock_session_maker, mock_resolve):
        """Old log_request still functions for backward compat."""
        mock_resolve.return_value = uuid.uuid4()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = mock_session

        await log_request(
            client_id="legacy",
            policy_name="balanced",
            model="llama3.1:8b",
            messages=[{"role": "user", "content": "test"}],
        )

        row = mock_session.add.call_args[0][0]
        assert row.client_id == "legacy"

    @pytest.mark.asyncio
    @patch("src.services.request_logger._resolve_policy_id", new_callable=AsyncMock)
    async def test_unknown_policy_warning(self, mock_resolve):
        """log_request_from_state handles unknown policy name gracefully."""
        mock_resolve.return_value = None

        state = _sample_state()
        state["policy_name"] = "nonexistent"

        # Should not raise — returns early with a warning
        await log_request_from_state(state)
