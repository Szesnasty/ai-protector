"""Tests for Presidio PII scanner node."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.nodes.presidio import (
    get_analyzer,
    mask_pii_in_messages,
    presidio_node,
    reset_analyzer,
    reset_anonymizer,
)


@pytest.fixture(autouse=True)
def _reset():
    """Reset engine singletons before each test."""
    reset_analyzer()
    reset_anonymizer()
    yield
    reset_analyzer()
    reset_anonymizer()


def _base_state(
    user_message: str = "Hello, how are you?",
    *,
    pii_action: str = "flag",
    enable: bool = True,
    risk_flags: dict | None = None,
    messages: list[dict] | None = None,
) -> dict:
    """Minimal pipeline state for presidio_node."""
    return {
        "request_id": "test-1",
        "user_message": user_message,
        "messages": messages or [{"role": "user", "content": user_message}],
        "policy_config": {"thresholds": {"pii_action": pii_action}},
        "risk_flags": risk_flags or {},
        "scanner_results": {},
        "errors": [],
    }


def _mock_result(entity_type: str, start: int, end: int, score: float = 0.85):
    """Create a mock RecognizerResult."""
    r = MagicMock()
    r.entity_type = entity_type
    r.start = start
    r.end = end
    r.score = score
    return r


def _mock_analyzer(results: list):
    """Create a mock AnalyzerEngine."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = results
    return analyzer


def _mock_anonymizer(anonymized_text: str):
    """Create a mock AnonymizerEngine."""
    anonymizer = MagicMock()
    anon_result = MagicMock()
    anon_result.text = anonymized_text
    anonymizer.anonymize.return_value = anon_result
    return anonymizer


# ── Detection Tests ───────────────────────────────────────────────────


class TestEmailDetection:
    """Email address → pii=[EMAIL_ADDRESS]."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_email_detected(self, mock_get):
        mock_get.return_value = _mock_analyzer([
            _mock_result("EMAIL_ADDRESS", 12, 28, score=0.95),
        ])
        state = _base_state("My email is john@example.com")
        result = await presidio_node(state)

        assert result["risk_flags"]["pii"] == ["EMAIL_ADDRESS"]
        assert result["risk_flags"]["pii_count"] == 1
        entities = result["scanner_results"]["presidio"]["entities"]
        assert len(entities) == 1
        assert entities[0]["entity_type"] == "EMAIL_ADDRESS"
        assert entities[0]["score"] == 0.95


class TestPhoneDetection:
    """Phone number → pii=[PHONE_NUMBER]."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_phone_detected(self, mock_get):
        mock_get.return_value = _mock_analyzer([
            _mock_result("PHONE_NUMBER", 14, 22, score=0.75),
        ])
        state = _base_state("Call me at 555-0123")
        result = await presidio_node(state)

        assert result["risk_flags"]["pii"] == ["PHONE_NUMBER"]
        assert result["risk_flags"]["pii_count"] == 1


class TestSSNDetection:
    """SSN → pii=[US_SSN]."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_ssn_detected(self, mock_get):
        mock_get.return_value = _mock_analyzer([
            _mock_result("US_SSN", 10, 21, score=0.85),
        ])
        state = _base_state("My SSN is 123-45-6789")
        result = await presidio_node(state)

        assert result["risk_flags"]["pii"] == ["US_SSN"]
        assert result["risk_flags"]["pii_count"] == 1


class TestNoPII:
    """No PII present → no risk flags added."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_no_pii_clean(self, mock_get):
        mock_get.return_value = _mock_analyzer([])
        state = _base_state("Hello, how are you?")
        result = await presidio_node(state)

        assert "pii" not in result["risk_flags"]
        assert "pii_count" not in result["risk_flags"]
        entities = result["scanner_results"]["presidio"]["entities"]
        assert entities == []


class TestMultiplePII:
    """Multiple PII entities detected."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_multiple_entities(self, mock_get):
        mock_get.return_value = _mock_analyzer([
            _mock_result("EMAIL_ADDRESS", 12, 28, score=0.95),
            _mock_result("PHONE_NUMBER", 40, 52, score=0.75),
            _mock_result("PERSON", 0, 10, score=0.8),
        ])
        state = _base_state("John Smith john@example.com call me at 555-012-3456")
        result = await presidio_node(state)

        assert result["risk_flags"]["pii_count"] == 3
        assert "EMAIL_ADDRESS" in result["risk_flags"]["pii"]
        assert "PHONE_NUMBER" in result["risk_flags"]["pii"]
        assert "PERSON" in result["risk_flags"]["pii"]


# ── Masking Tests ─────────────────────────────────────────────────────


class TestMaskAction:
    """pii_action=mask → modified_messages with anonymized text."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_anonymizer")
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_mask_produces_modified_messages(self, mock_analyzer, mock_anonymizer):
        mock_analyzer.return_value = _mock_analyzer([
            _mock_result("EMAIL_ADDRESS", 12, 28, score=0.95),
        ])
        mock_anonymizer.return_value = _mock_anonymizer("My email is <EMAIL_ADDRESS>")

        state = _base_state("My email is john@example.com", pii_action="mask")
        result = await presidio_node(state)

        assert result["modified_messages"] is not None
        user_msg = next(m for m in result["modified_messages"] if m["role"] == "user")
        assert user_msg["content"] == "My email is <EMAIL_ADDRESS>"

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_anonymizer")
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_mask_does_not_mutate_original(self, mock_analyzer, mock_anonymizer):
        mock_analyzer.return_value = _mock_analyzer([
            _mock_result("EMAIL_ADDRESS", 12, 28, score=0.95),
        ])
        mock_anonymizer.return_value = _mock_anonymizer("My email is <EMAIL_ADDRESS>")

        original_messages = [{"role": "user", "content": "My email is john@example.com"}]
        state = _base_state(
            "My email is john@example.com",
            pii_action="mask",
            messages=original_messages,
        )
        await presidio_node(state)

        # Original should be unchanged
        assert original_messages[0]["content"] == "My email is john@example.com"

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_flag_no_modified_messages(self, mock_get):
        mock_get.return_value = _mock_analyzer([
            _mock_result("EMAIL_ADDRESS", 12, 28, score=0.95),
        ])
        state = _base_state("My email is john@example.com", pii_action="flag")
        result = await presidio_node(state)

        assert "modified_messages" not in result


class TestMaskPiiHelper:
    """Direct tests for mask_pii_in_messages()."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_anonymizer")
    async def test_masks_correct_message(self, mock_get):
        mock_get.return_value = _mock_anonymizer("Hi, I'm <PERSON>")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hi, I'm John Smith"},
        ]
        results = [_mock_result("PERSON", 7, 17)]
        masked = await mask_pii_in_messages(messages, "Hi, I'm John Smith", results)

        assert masked[0]["content"] == "You are a helpful assistant."
        assert masked[1]["content"] == "Hi, I'm <PERSON>"


# ── Error Handling ────────────────────────────────────────────────────


class TestErrorHandling:
    """Analyzer errors → logged, not raised."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_analyzer_exception_handled(self, mock_get):
        mock_get.side_effect = RuntimeError("spaCy model not found")
        state = _base_state("My email is john@example.com")
        result = await presidio_node(state)

        # Should not crash
        assert "error" in result["scanner_results"]["presidio"]
        assert any("presidio" in e for e in result["errors"])

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_anonymizer")
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_masking_error_handled(self, mock_analyzer, mock_anonymizer):
        mock_analyzer.return_value = _mock_analyzer([
            _mock_result("EMAIL_ADDRESS", 12, 28, score=0.95),
        ])
        mock_anonymizer.side_effect = RuntimeError("anonymizer failed")

        state = _base_state("My email is john@example.com", pii_action="mask")
        result = await presidio_node(state)

        # PII should still be detected
        assert result["risk_flags"]["pii"] == ["EMAIL_ADDRESS"]
        # Error logged
        assert any("presidio.mask" in e for e in result["errors"])
        # No modified_messages
        assert "modified_messages" not in result


# ── Disabled Toggle ───────────────────────────────────────────────────


class TestDisabled:
    """Presidio disabled → no analysis."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_settings")
    async def test_disabled_skips(self, mock_settings):
        mock_settings.return_value = MagicMock(enable_presidio=False)
        state = _base_state()
        result = await presidio_node(state)

        assert result.get("scanner_results", {}).get("presidio") is None

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_empty_message_skips(self, mock_get):
        state = _base_state(user_message="")
        state["messages"] = [{"role": "user", "content": ""}]
        await presidio_node(state)

        mock_get.assert_not_called()


# ── Preserves Existing Results ────────────────────────────────────────


class TestPreservesExisting:
    """Presidio node preserves existing risk_flags and scanner_results."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_preserves_existing_flags(self, mock_get):
        mock_get.return_value = _mock_analyzer([
            _mock_result("EMAIL_ADDRESS", 12, 28, score=0.95),
        ])
        state = _base_state(
            "My email is john@example.com",
            risk_flags={"injection": 0.8},
        )
        result = await presidio_node(state)

        assert result["risk_flags"]["injection"] == 0.8
        assert result["risk_flags"]["pii"] == ["EMAIL_ADDRESS"]

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_preserves_existing_scanner_results(self, mock_get):
        mock_get.return_value = _mock_analyzer([])
        state = _base_state()
        state["scanner_results"] = {"llm_guard": {"PromptInjection": {"is_valid": True}}}
        result = await presidio_node(state)

        assert "llm_guard" in result["scanner_results"]
        assert "presidio" in result["scanner_results"]


# ── timing ────────────────────────────────────────────────────────────


class TestTiming:
    """Node records execution time."""

    @pytest.mark.asyncio
    @patch("src.pipeline.nodes.presidio.get_analyzer")
    async def test_records_timing(self, mock_get):
        mock_get.return_value = _mock_analyzer([])
        state = _base_state()
        result = await presidio_node(state)

        assert "presidio" in result.get("node_timings", {})


# ── Lazy init ─────────────────────────────────────────────────────────


class TestLazyInit:
    """Test lazy engine initialization."""

    @patch("src.pipeline.nodes.presidio.get_settings")
    @patch("src.pipeline.nodes.presidio.AnalyzerEngine", create=True)
    @patch("src.pipeline.nodes.presidio.NlpEngineProvider", create=True)
    def test_get_analyzer_caches(self, _mock_provider_cls, _mock_engine_cls, mock_settings):
        """get_analyzer() should return same instance on repeated calls."""
        # For caching test we directly inject a mock
        import src.pipeline.nodes.presidio as mod

        fake = MagicMock()
        mod._analyzer = fake
        result = get_analyzer()
        assert result is fake

    def test_reset_clears_analyzer(self):
        import src.pipeline.nodes.presidio as mod

        mod._analyzer = MagicMock()
        reset_analyzer()
        assert mod._analyzer is None

    def test_reset_clears_anonymizer(self):
        import src.pipeline.nodes.presidio as mod

        mod._anonymizer = MagicMock()
        reset_anonymizer()
        assert mod._anonymizer is None
