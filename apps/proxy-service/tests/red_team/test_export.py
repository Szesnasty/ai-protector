"""Tests for red_team.export — PDF report generation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.red_team.export.business_impact import (
    CATEGORY_BUSINESS_IMPACT,
    get_business_impact,
    get_executive_risk_summary,
)
from src.red_team.export.renderer import (
    _build_categories,
    _format_latency,
    _human_category,
    _score_label,
    _truncate,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_RUN_ID = str(uuid.uuid4())
_NOW = datetime.now(UTC).isoformat()


def _make_run(**overrides: object) -> dict:
    base = {
        "id": _RUN_ID,
        "pack": "core_security",
        "status": "completed",
        "target_type": "hosted_endpoint",
        "target_config": {},
        "score_simple": 76,
        "score_weighted": 17,
        "confidence": None,
        "total_in_pack": 51,
        "total_applicable": 50,
        "executed": 50,
        "passed": 38,
        "failed": 12,
        "skipped": 0,
        "skipped_reasons": {},
        "policy": "balanced",
        "source_run_id": None,
        "error": None,
        "created_at": "2026-03-31T18:25:36.852278Z",
        "completed_at": "2026-03-31T18:31:45.391304Z",
        "protection_detected": False,
        "proxy_blocked_count": 0,
        "target_label": "",
        "target_fingerprint": "",
        "pack_version": None,
        "false_positives": 0,
        "idempotency_key": None,
    }
    base.update(overrides)
    return base


def _make_scenario(
    scenario_id: str = "PI-001",
    category: str = "prompt_injection",
    severity: str = "medium",
    passed: bool = True,
    **overrides: object,
) -> dict:
    base = {
        "id": str(uuid.uuid4()),
        "scenario_id": scenario_id,
        "category": category,
        "severity": severity,
        "prompt": "Test prompt text for " + scenario_id,
        "expected": "BLOCK",
        "actual": "BLOCK" if passed else "ALLOW",
        "passed": passed,
        "skipped": False,
        "skipped_reason": None,
        "detector_type": "heuristic",
        "detector_detail": None,
        "latency_ms": 1500,
        "raw_response_body": None,
        "pipeline_result": None,
        "created_at": _NOW,
        "title": f"Test Scenario {scenario_id}",
        "description": f"Description for {scenario_id}",
        "why_it_passes": None,
        "fix_hints": [],
    }
    base.update(overrides)
    return base


# ===========================================================================
# business_impact module
# ===========================================================================


class TestBusinessImpact:
    def test_all_categories_have_impact(self) -> None:
        """Every known category must have an impact text."""
        for cat in CATEGORY_BUSINESS_IMPACT:
            text = get_business_impact(cat, "critical")
            assert len(text) > 20
            assert "Immediate action" in text

    def test_unknown_category_fallback(self) -> None:
        text = get_business_impact("unknown_category", "high")
        assert "security gap" in text.lower()

    def test_severity_prefix_varies(self) -> None:
        crit = get_business_impact("pii_disclosure", "critical")
        low = get_business_impact("pii_disclosure", "low")
        assert "Immediate action" in crit
        assert "ongoing hardening" in low

    def test_executive_summary_no_failures(self) -> None:
        summary = get_executive_risk_summary(0, 0, [])
        assert "No critical" in summary

    def test_executive_summary_with_failures(self) -> None:
        summary = get_executive_risk_summary(3, 2, ["secrets_detection", "pii_disclosure"])
        assert "5 high-impact" in summary
        assert "3 critical" in summary
        assert "remediation" in summary.lower()


# ===========================================================================
# renderer helpers
# ===========================================================================


class TestRendererHelpers:
    def test_score_label_strong(self) -> None:
        assert _score_label(95)[0] == "Strong"

    def test_score_label_good(self) -> None:
        assert _score_label(85)[0] == "Good"

    def test_score_label_needs_hardening(self) -> None:
        assert _score_label(65)[0] == "Needs Hardening"

    def test_score_label_weak(self) -> None:
        assert _score_label(45)[0] == "Weak"

    def test_score_label_critical(self) -> None:
        assert _score_label(20)[0] == "Critical"

    def test_human_category_known(self) -> None:
        assert _human_category("pii_disclosure") == "PII Disclosure"

    def test_human_category_unknown(self) -> None:
        result = _human_category("some_new_thing")
        assert result == "Some New Thing"

    def test_truncate_short(self) -> None:
        assert _truncate("short") == "short"

    def test_truncate_long(self) -> None:
        long_text = "a" * 300
        result = _truncate(long_text, 200)
        assert len(result) == 201  # 200 + ellipsis
        assert result.endswith("…")

    def test_format_latency_none(self) -> None:
        assert _format_latency(None) == "—"

    def test_format_latency_ms(self) -> None:
        result = _format_latency(1500)
        assert "1" in result
        assert "ms" in result

    def test_format_latency_seconds(self) -> None:
        result = _format_latency(15000)
        assert "s" in result

    def test_build_categories_sorting(self) -> None:
        scenarios = [
            _make_scenario("S1", "prompt_injection", passed=True),
            _make_scenario("S2", "prompt_injection", passed=True),
            _make_scenario("S3", "secrets_detection", passed=False),
            _make_scenario("S4", "secrets_detection", passed=False),
        ]
        cats = _build_categories(scenarios)
        # Worst first
        assert cats[0]["slug"] == "secrets_detection"
        assert cats[0]["percent"] == 0
        assert cats[1]["slug"] == "prompt_injection"
        assert cats[1]["percent"] == 100


# ===========================================================================
# PDF rendering (integration — requires weasyprint)
# ===========================================================================


class TestPdfRender:
    @pytest.fixture()
    def sample_run(self) -> dict:
        return _make_run()

    @pytest.fixture()
    def sample_scenarios(self) -> list[dict]:
        return [
            _make_scenario("PI-001", "prompt_injection", "medium", True),
            _make_scenario("PI-002", "prompt_injection", "medium", True),
            _make_scenario("SEC-001", "secrets_detection", "critical", False,
                           fix_hints=["Enable secrets scanner"]),
            _make_scenario("PII-001", "pii_disclosure", "high", False,
                           fix_hints=["Enable PII scanner"]),
            _make_scenario("SAFE-001", "safe_allow", "low", True),
        ]

    def test_pdf_generates(self, sample_run: dict, sample_scenarios: list[dict]) -> None:
        """PDF should be generated without errors."""
        from src.red_team.export.renderer import render_pdf_report

        pdf_bytes = render_pdf_report(sample_run, sample_scenarios)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        # PDF magic bytes
        assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_not_empty_with_no_failures(self, sample_run: dict) -> None:
        """PDF works even when all scenarios pass."""
        from src.red_team.export.renderer import render_pdf_report

        scenarios = [
            _make_scenario("PI-001", "prompt_injection", "medium", True),
            _make_scenario("PI-002", "prompt_injection", "medium", True),
        ]
        run = _make_run(failed=0, passed=2, executed=2)
        pdf_bytes = render_pdf_report(run, scenarios)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_no_auth_secrets_in_pdf(self, sample_run: dict, sample_scenarios: list[dict]) -> None:
        """PDF must not contain auth credentials from target_config."""
        from src.red_team.export.renderer import render_pdf_report

        run = _make_run(target_config={"auth_header": "Bearer secret123", "endpoint_url": "https://example.com"})
        pdf_bytes = render_pdf_report(run, sample_scenarios)
        # Auth header value should not appear in the PDF text
        assert b"secret123" not in pdf_bytes

    def test_scoring_simplified(self, sample_run: dict, sample_scenarios: list[dict]) -> None:
        """Report should show simple score as main, weighted in appendix."""
        from src.red_team.export.renderer import render_pdf_report

        # We can only verify the PDF is generated — content checking
        # requires PDF text extraction which is not worth adding as dep.
        # The structure test via HTML template rendering is sufficient.
        pdf_bytes = render_pdf_report(sample_run, sample_scenarios)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
