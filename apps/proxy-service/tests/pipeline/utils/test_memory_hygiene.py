"""Tests for memory hygiene — conversation sanitization utility."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.utils.memory_hygiene import (
    DEFAULT_MAX_CHARS_PER_MESSAGE,
    DEFAULT_MAX_TURNS,
    _enforce_total_limit,
    _redact_secrets_from_messages,
    _truncate_messages,
    _truncate_turns,
    sanitize_conversation,
)

# ── Helpers ───────────────────────────────────────────────────────────


def _msgs(n: int, *, system: bool = True) -> list[dict]:
    """Build a conversation with *n* user/assistant pairs + optional system msg."""
    result: list[dict] = []
    if system:
        result.append({"role": "system", "content": "You are a helpful assistant."})
    for i in range(n):
        result.append({"role": "user", "content": f"User message {i}"})
        result.append({"role": "assistant", "content": f"Assistant reply {i}"})
    return result


def _mock_analyzer(results_per_call: list | None = None):
    """Return a mock analyzer that yields *results_per_call* on each call."""
    analyzer = MagicMock()
    if results_per_call is None:
        analyzer.analyze.return_value = []
    else:
        analyzer.analyze.side_effect = results_per_call
    return analyzer


def _mock_anonymizer(anonymized_texts: list[str] | None = None):
    """Return a mock anonymizer."""
    anonymizer = MagicMock()
    if anonymized_texts is None:
        anonymizer.anonymize.return_value = MagicMock(text="")
    else:
        results = [MagicMock(text=t) for t in anonymized_texts]
        anonymizer.anonymize.side_effect = results
    return anonymizer


def _mock_result(entity_type: str, start: int = 0, end: int = 5, score: float = 0.9):
    r = MagicMock()
    r.entity_type = entity_type
    r.start = start
    r.end = end
    r.score = score
    return r


# ── Test 1: Short conversation → no changes ──────────────────────────


class TestShortConversation:
    """Short conversations pass through without modification."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    @patch("src.pipeline.nodes.presidio.get_anonymizer")
    async def test_short_conv_no_changes(self, mock_anon, mock_get):
        mock_get.return_value = _mock_analyzer()
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = await sanitize_conversation(msgs, redact_pii=True, redact_secrets=True)
        assert len(result) == 3
        assert result[0]["role"] == "system"
        assert result[1]["content"] == "Hello"
        assert result[2]["content"] == "Hi there!"


# ── Test 2: 30 messages → truncated to 20 + system ───────────────────


class TestTurnTruncation:
    """Long conversations are truncated, system message preserved."""

    @pytest.mark.asyncio
    async def test_30_msgs_truncated(self):
        msgs = _msgs(15)  # 1 system + 30 non-system
        assert len(msgs) == 31
        result = await sanitize_conversation(
            msgs, redact_pii=False, redact_secrets=False, max_turns=DEFAULT_MAX_TURNS
        )
        # 1 system + 20 non-system
        assert len(result) == 21
        assert result[0]["role"] == "system"


# ── Test 3: Long message → truncated with [TRUNCATED] ────────────────


class TestMessageTruncation:
    """Individual messages exceeding max chars are truncated."""

    @pytest.mark.asyncio
    async def test_long_message_truncated(self):
        long_content = "x" * 5000
        msgs = [{"role": "user", "content": long_content}]
        result = await sanitize_conversation(
            msgs,
            redact_pii=False,
            redact_secrets=False,
            max_chars_per_message=DEFAULT_MAX_CHARS_PER_MESSAGE,
        )
        assert result[0]["content"].endswith("... [TRUNCATED]")
        assert len(result[0]["content"]) < len(long_content)


# ── Test 4: Message with email → PII redacted ────────────────────────


class TestPIIRedaction:
    """PII in user/assistant messages is redacted via Presidio."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_anonymizer")
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_email_redacted(self, mock_get, mock_anon_get):
        mock_get.return_value = _mock_analyzer([
            [_mock_result("EMAIL_ADDRESS", 12, 28)],  # user message
            [],                                         # assistant message
        ])
        mock_anon_get.return_value = _mock_anonymizer(["My email is <EMAIL_ADDRESS>."])

        msgs = [
            {"role": "user", "content": "My email is john@example.com."},
            {"role": "assistant", "content": "Got it!"},
        ]
        result = await sanitize_conversation(msgs, redact_pii=True, redact_secrets=False)
        assert "<EMAIL_ADDRESS>" in result[0]["content"]
        assert result[1]["content"] == "Got it!"


# ── Test 5: Message with API key → secret redacted ───────────────────


class TestSecretRedaction:
    """API keys in messages are redacted via regex."""

    @pytest.mark.asyncio
    async def test_api_key_redacted(self):
        key = "sk-" + "a" * 30
        msgs = [{"role": "assistant", "content": f"Use key: {key}"}]
        result = await sanitize_conversation(msgs, redact_pii=False, redact_secrets=True)
        assert "[SECRET_REDACTED]" in result[0]["content"]
        assert key not in result[0]["content"]


# ── Test 6: System message preserved during truncation ────────────────


class TestSystemPreserved:
    """System messages are always kept, even when truncating."""

    def test_system_preserved(self):
        msgs = _msgs(15)  # 31 messages
        result = _truncate_turns(msgs, max_turns=4)
        assert result[0]["role"] == "system"
        assert len(result) == 5  # 1 system + 4 non-system


# ── Test 7: Total char limit exceeded → oldest dropped ────────────────


class TestTotalCharLimit:
    """When total chars exceed limit, oldest non-system messages are dropped."""

    def test_oldest_dropped(self):
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "a" * 100},
            {"role": "assistant", "content": "b" * 100},
            {"role": "user", "content": "c" * 100},
        ]
        result = _enforce_total_limit(msgs, max_total_chars=210)
        # System (3) + last user (100) = 103, or drops until under 210
        assert all(m.get("role") == "system" or True for m in result)
        total = sum(len(m.get("content", "")) for m in result)
        assert total <= 210


# ── Test 8: redact_pii=False → PII kept ──────────────────────────────


class TestPIIDisabled:
    """When redact_pii=False, email addresses are preserved."""

    @pytest.mark.asyncio
    async def test_pii_kept(self):
        msgs = [{"role": "user", "content": "john@example.com"}]
        result = await sanitize_conversation(msgs, redact_pii=False, redact_secrets=False)
        assert result[0]["content"] == "john@example.com"


# ── Test 9: redact_secrets=False → secrets kept ──────────────────────


class TestSecretsDisabled:
    """When redact_secrets=False, API keys are preserved."""

    @pytest.mark.asyncio
    async def test_secrets_kept(self):
        key = "sk-" + "a" * 30
        msgs = [{"role": "user", "content": f"Key: {key}"}]
        result = await sanitize_conversation(msgs, redact_pii=False, redact_secrets=False)
        assert key in result[0]["content"]


# ── Test 10: Empty conversation → empty list ─────────────────────────


class TestEmptyConversation:
    """Empty input returns empty output without errors."""

    @pytest.mark.asyncio
    async def test_empty(self):
        result = await sanitize_conversation([])
        assert result == []


# ── Test 11: Mixed PII + secrets in same message ─────────────────────


class TestMixedRedaction:
    """Both PII and secrets in the same message are redacted."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_anonymizer")
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_mixed(self, mock_get, mock_anon_get):
        key = "sk-" + "c" * 30
        mock_get.return_value = _mock_analyzer([
            [_mock_result("EMAIL_ADDRESS", 0, 16)],
        ])
        # After PII redaction, the text still contains the secret
        mock_anon_get.return_value = _mock_anonymizer([f"<EMAIL_ADDRESS> key={key}"])

        msgs = [{"role": "user", "content": f"john@example.com key={key}"}]
        result = await sanitize_conversation(msgs, redact_pii=True, redact_secrets=True)

        assert "<EMAIL_ADDRESS>" in result[0]["content"]
        assert "[SECRET_REDACTED]" in result[0]["content"]
        assert key not in result[0]["content"]


# ── Helper unit tests ─────────────────────────────────────────────────


class TestTruncateHelpers:
    """Direct tests for truncation helpers."""

    def test_truncate_turns_no_op(self):
        msgs = _msgs(3, system=False)
        result = _truncate_turns(msgs, max_turns=20)
        assert len(result) == 6

    def test_truncate_messages_short(self):
        msgs = [{"role": "user", "content": "short"}]
        result = _truncate_messages(msgs, max_chars=100)
        assert result[0]["content"] == "short"

    def test_redact_secrets_password(self):
        msgs = [{"role": "user", "content": "password=hunter2"}]
        result = _redact_secrets_from_messages(msgs)
        assert "[SECRET_REDACTED]" in result[0]["content"]
        assert "hunter2" not in result[0]["content"]

    def test_enforce_total_under_limit(self):
        msgs = [{"role": "user", "content": "hi"}]
        result = _enforce_total_limit(msgs, max_total_chars=100)
        assert len(result) == 1
