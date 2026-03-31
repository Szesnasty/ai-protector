"""Tests for stage-aware evaluation: ingress_block, ingress_redact, output_leak, tool_abuse, safe_allow.

Covers:
 - ScenarioStage enum
 - _is_proxy_block_response helper
 - Stage-routed evaluation in RunEngine._execute_scenario
 - New pack loading with stage field
 - Canary substitution in canary-enabled packs
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.red_team.engine import RunConfig, RunEngine, RunState
from src.red_team.engine.protocols import HttpResponse
from src.red_team.engine.run_engine import (
    _has_proxy_fingerprint,
    _is_proxy_block_response,
    _substitute_canary_in_scenario,
)
from src.red_team.packs import filter_pack, load_pack
from src.red_team.packs.loader import TargetConfig, clear_cache
from src.red_team.schemas import Scenario
from src.red_team.schemas.dataclasses import RawTargetResponse
from src.red_team.schemas.enums import ScenarioStage

# ---------------------------------------------------------------------------
# Path to real pack data
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "red_team" / "packs" / "data"


@pytest.fixture(autouse=True)
def _clear_pack_cache():
    clear_cache()
    yield
    clear_cache()


# ===========================================================================
# ScenarioStage enum
# ===========================================================================


class TestScenarioStageEnum:
    def test_values(self) -> None:
        assert ScenarioStage.INGRESS_BLOCK.value == "ingress_block"
        assert ScenarioStage.INGRESS_REDACT.value == "ingress_redact"
        assert ScenarioStage.OUTPUT_LEAK.value == "output_leak"
        assert ScenarioStage.TOOL_ABUSE.value == "tool_abuse"
        assert ScenarioStage.SAFE_ALLOW.value == "safe_allow"

    def test_from_string(self) -> None:
        assert ScenarioStage("ingress_block") == ScenarioStage.INGRESS_BLOCK
        assert ScenarioStage("output_leak") == ScenarioStage.OUTPUT_LEAK


# ===========================================================================
# Scenario stage field
# ===========================================================================


class TestScenarioStageField:
    def test_default_is_output_leak(self) -> None:
        s = Scenario(
            id="T-001",
            title="Test",
            category="prompt_injection",
            severity="high",
            applicable_to=["chatbot_api"],
            prompt="test",
            expected="BLOCK",
            detector={"type": "keyword", "keywords": ["x"], "match_means": "fail", "case_sensitive": False},
        )
        assert s.stage == ScenarioStage.OUTPUT_LEAK

    def test_explicit_ingress_block(self) -> None:
        s = Scenario(
            id="T-002",
            title="Test",
            category="secrets_detection",
            severity="critical",
            applicable_to=["chatbot_api"],
            prompt="test",
            expected="BLOCK",
            stage="ingress_block",
            sensitive_entities=["aws_access_key"],
            detector={"type": "regex", "pattern": "AKIA.*", "match_means": "fail"},
        )
        assert s.stage == ScenarioStage.INGRESS_BLOCK
        assert s.sensitive_entities == ["aws_access_key"]

    def test_sensitive_entities_default_empty(self) -> None:
        s = Scenario(
            id="T-003",
            title="Test",
            category="prompt_injection",
            severity="high",
            applicable_to=["chatbot_api"],
            prompt="test",
            expected="BLOCK",
            detector={"type": "keyword", "keywords": ["x"], "match_means": "fail", "case_sensitive": False},
        )
        assert s.sensitive_entities == []


# ===========================================================================
# _is_proxy_block_response
# ===========================================================================


class TestIsProxyBlockResponse:
    # -- Tier 1: x-decision header ----------------------------------------

    def test_x_decision_block_header(self) -> None:
        """x-decision: BLOCK is definitive proxy signal regardless of status."""
        r = HttpResponse(status_code=403, body="Forbidden", headers={"x-decision": "BLOCK"})
        assert _is_proxy_block_response(r) is True

    def test_x_decision_block_on_200(self) -> None:
        """Even a 200 with x-decision: BLOCK is a proxy block."""
        r = HttpResponse(status_code=200, body="ok", headers={"x-decision": "BLOCK"})
        assert _is_proxy_block_response(r) is True

    # -- Tier 2: 403/451 with fingerprint ---------------------------------

    def test_403_with_fingerprint_is_block(self) -> None:
        r = HttpResponse(status_code=403, body="Forbidden", headers={"x-risk-score": "0.9"})
        assert _is_proxy_block_response(r) is True

    def test_451_with_fingerprint_is_block(self) -> None:
        r = HttpResponse(status_code=451, body="Unavailable", headers={"x-decision": "DENY"})
        assert _is_proxy_block_response(r) is True

    # -- Tier 2 negative: bare 403/451 without fingerprint ----------------

    def test_bare_403_is_not_block(self) -> None:
        """A bare 403 from the target (no proxy headers) is NOT a proxy block."""
        r = HttpResponse(status_code=403, body="Forbidden")
        assert _is_proxy_block_response(r) is False

    def test_bare_451_is_not_block(self) -> None:
        r = HttpResponse(status_code=451, body="Unavailable For Legal Reasons")
        assert _is_proxy_block_response(r) is False

    # -- Tier 3: 4xx + fingerprint + body markers -------------------------

    def test_400_with_fingerprint_and_marker(self) -> None:
        r = HttpResponse(
            status_code=400,
            body='{"error": "Request blocked by policy"}',
            headers={"x-risk-score": "0.85"},
        )
        assert _is_proxy_block_response(r) is True

    def test_429_with_fingerprint_and_marker(self) -> None:
        r = HttpResponse(
            status_code=429,
            body="Access denied by security policy",
            headers={"x-decision": "THROTTLE"},
        )
        assert _is_proxy_block_response(r) is True

    # -- Tier 3 negative: 4xx + markers but NO fingerprint ----------------

    def test_400_with_marker_but_no_fingerprint(self) -> None:
        """4xx with body markers but no proxy headers is a target error, not proxy."""
        r = HttpResponse(status_code=400, body='{"error": "Request blocked by policy"}')
        assert _is_proxy_block_response(r) is False

    def test_429_with_marker_but_no_fingerprint(self) -> None:
        r = HttpResponse(status_code=429, body="Access denied by security policy")
        assert _is_proxy_block_response(r) is False

    # -- Always false cases -----------------------------------------------

    def test_200_with_block_marker(self) -> None:
        """200 with 'blocked' in body is a model refusal, not a proxy block."""
        r = HttpResponse(status_code=200, body='{"error": "Request blocked by policy"}')
        assert _is_proxy_block_response(r) is False

    def test_200_normal_response(self) -> None:
        r = HttpResponse(status_code=200, body="I cannot help with that request.")
        assert _is_proxy_block_response(r) is False

    def test_200_with_denied_marker(self) -> None:
        """200 with 'denied' in body is a model refusal, not a proxy block."""
        r = HttpResponse(status_code=200, body="Access denied by security policy")
        assert _is_proxy_block_response(r) is False

    def test_500_not_block(self) -> None:
        r = HttpResponse(status_code=500, body="Internal Server Error")
        assert _is_proxy_block_response(r) is False


# ===========================================================================
# _has_proxy_fingerprint
# ===========================================================================


class TestHasProxyFingerprint:
    def test_x_decision_header(self) -> None:
        r = HttpResponse(status_code=200, body="ok", headers={"x-decision": "ALLOW"})
        assert _has_proxy_fingerprint(r) is True

    def test_x_risk_score_header(self) -> None:
        r = HttpResponse(status_code=403, body="blocked", headers={"x-risk-score": "0.95"})
        assert _has_proxy_fingerprint(r) is True

    def test_no_proxy_headers(self) -> None:
        r = HttpResponse(status_code=200, body="Hello", headers={"content-type": "application/json"})
        assert _has_proxy_fingerprint(r) is False

    def test_empty_headers(self) -> None:
        r = HttpResponse(status_code=200, body="Hello")
        assert _has_proxy_fingerprint(r) is False


# ===========================================================================
# Pack loading with stage
# ===========================================================================


class TestNewPacksLoad:
    def test_core_verified_loads(self) -> None:
        pack = load_pack("core_verified", packs_dir=_DATA_DIR)
        assert pack.name == "core_verified"
        assert len(pack.scenarios) == 23
        assert pack.system_prompt is not None
        assert "${CANARY}" in pack.system_prompt

    def test_unsafe_output_loads(self) -> None:
        pack = load_pack("unsafe_output", packs_dir=_DATA_DIR)
        assert pack.name == "unsafe_output"
        assert len(pack.scenarios) == 5

    def test_extended_advisory_loads(self) -> None:
        pack = load_pack("extended_advisory", packs_dir=_DATA_DIR)
        assert pack.name == "extended_advisory"
        assert len(pack.scenarios) == 25

    def test_core_verified_stages(self) -> None:
        pack = load_pack("core_verified", packs_dir=_DATA_DIR)
        stages = {s.id: s.stage for s in pack.scenarios}
        # Secrets → ingress_block
        assert stages["SEC-001"] == ScenarioStage.INGRESS_BLOCK
        assert stages["SEC-004"] == ScenarioStage.INGRESS_BLOCK
        # PII → ingress_block
        assert stages["PII-001"] == ScenarioStage.INGRESS_BLOCK
        assert stages["PII-002"] == ScenarioStage.INGRESS_BLOCK
        # Leak → output_leak
        assert stages["LEAK-001"] == ScenarioStage.OUTPUT_LEAK
        assert stages["LEAK-005"] == ScenarioStage.OUTPUT_LEAK
        # Tool → tool_abuse
        assert stages["TOOL-001"] == ScenarioStage.TOOL_ABUSE
        # FP → safe_allow
        assert stages["FP-001"] == ScenarioStage.SAFE_ALLOW

    def test_core_verified_sensitive_entities(self) -> None:
        pack = load_pack("core_verified", packs_dir=_DATA_DIR)
        by_id = {s.id: s for s in pack.scenarios}
        assert "aws_access_key" in by_id["SEC-001"].sensitive_entities
        assert "credit_card" in by_id["PII-002"].sensitive_entities
        assert by_id["LEAK-001"].sensitive_entities == []  # output_leak has no ingress entities

    def test_unsafe_output_all_output_leak(self) -> None:
        pack = load_pack("unsafe_output", packs_dir=_DATA_DIR)
        for s in pack.scenarios:
            assert s.stage == ScenarioStage.OUTPUT_LEAK, f"{s.id} should be output_leak"

    def test_extended_advisory_ingress_scenarios(self) -> None:
        pack = load_pack("extended_advisory", packs_dir=_DATA_DIR)
        by_id = {s.id: s for s in pack.scenarios}
        assert by_id["EXT-021"].stage == ScenarioStage.INGRESS_BLOCK
        assert by_id["EXT-022"].stage == ScenarioStage.INGRESS_BLOCK
        assert by_id["EXT-024"].stage == ScenarioStage.SAFE_ALLOW

    def test_all_packs_no_duplicate_ids(self) -> None:
        """IDs must be unique across all new packs."""
        all_ids: list[str] = []
        for name in ("core_verified", "unsafe_output", "extended_advisory"):
            pack = load_pack(name, packs_dir=_DATA_DIR)
            all_ids.extend(s.id for s in pack.scenarios)
        assert len(all_ids) == len(set(all_ids)), f"Duplicate IDs found: {[x for x in all_ids if all_ids.count(x) > 1]}"


# ===========================================================================
# Canary substitution
# ===========================================================================


class TestCanarySubstitution:
    def test_substitutes_in_exact_match(self) -> None:
        s = Scenario(
            id="L-001",
            title="Canary test",
            category="data_leakage_pii",
            severity="critical",
            applicable_to=["chatbot_api"],
            prompt="test",
            expected="BLOCK",
            detector={"type": "exact_match", "forbidden_strings": ["${CANARY}"], "match_means": "fail"},
        )
        result = _substitute_canary_in_scenario(s, "CANARY_ABCD1234")
        assert "CANARY_ABCD1234" in result.detector.forbidden_strings
        assert "${CANARY}" not in result.detector.forbidden_strings

    def test_no_canary_returns_same(self) -> None:
        s = Scenario(
            id="L-002",
            title="No canary",
            category="data_leakage_pii",
            severity="critical",
            applicable_to=["chatbot_api"],
            prompt="test",
            expected="BLOCK",
            detector={"type": "keyword", "keywords": ["leak"], "match_means": "fail", "case_sensitive": False},
        )
        result = _substitute_canary_in_scenario(s, "CANARY_ABCD1234")
        assert result is s  # Same object, no copy needed

    def test_original_unchanged(self) -> None:
        s = Scenario(
            id="L-003",
            title="Immutability test",
            category="data_leakage_pii",
            severity="critical",
            applicable_to=["chatbot_api"],
            prompt="test",
            expected="BLOCK",
            detector={"type": "exact_match", "forbidden_strings": ["${CANARY}"], "match_means": "fail"},
        )
        _ = _substitute_canary_in_scenario(s, "CANARY_XXXX9999")
        assert "${CANARY}" in s.detector.forbidden_strings


# ===========================================================================
# FilteredPack system_prompt pass-through
# ===========================================================================


class TestFilteredPackSystemPrompt:
    def test_system_prompt_passed_through(self) -> None:
        pack = load_pack("core_verified", packs_dir=_DATA_DIR)
        config = TargetConfig(agent_type="chatbot_api", safe_mode=False)
        filtered = filter_pack(pack, config)
        assert filtered.system_prompt is not None
        assert "${CANARY}" in filtered.system_prompt

    def test_no_system_prompt_for_unsafe_output(self) -> None:
        pack = load_pack("unsafe_output", packs_dir=_DATA_DIR)
        config = TargetConfig(agent_type="chatbot_api", safe_mode=False)
        filtered = filter_pack(pack, config)
        assert filtered.system_prompt is None


# ===========================================================================
# Integration: ingress_block in RunEngine
# ===========================================================================


class MockHttpClient:
    def __init__(
        self,
        status_code: int = 200,
        body: str = "I cannot help with that.",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.body = body
        self.headers = headers or {}

    async def send_prompt(self, prompt: str, target_config: dict[str, Any]) -> HttpResponse:
        return HttpResponse(
            status_code=self.status_code,
            body=self.body,
            headers=self.headers,
            latency_ms=50.0,
        )


class MockNormalizer:
    def normalize(self, http_response: HttpResponse, target_config: dict[str, Any]) -> RawTargetResponse:
        return RawTargetResponse(
            body_text=http_response.body,
            parsed_json=None,
            tool_calls=None,
            status_code=http_response.status_code,
            latency_ms=http_response.latency_ms,
            raw_body=http_response.body,
            provider_format="plain_text",
        )


class MockPersistence:
    def __init__(self) -> None:
        self.runs: dict[str, dict] = {}
        self.results: list[dict] = []
        self.active_runs: dict[str, dict] = {}
        self.idempotency_keys: dict[str, dict] = {}

    async def create_run(self, run_data: dict) -> str:
        self.runs[run_data["id"]] = run_data
        if run_data.get("state") in ("created", "running"):
            fp = run_data.get("target_fingerprint", "")
            self.active_runs[fp] = run_data
        return run_data["id"]

    async def update_run(self, run_id: str, updates: dict) -> None:
        if run_id in self.runs:
            self.runs[run_id].update(updates)
            if updates.get("state") in ("completed", "cancelled", "failed"):
                fp = self.runs[run_id].get("target_fingerprint", "")
                self.active_runs.pop(fp, None)

    async def persist_result(self, run_id: str, result_data: dict) -> None:
        result_data["run_id"] = run_id
        self.results.append(result_data)

    async def get_run(self, run_id: str) -> dict | None:
        return self.runs.get(run_id)

    async def find_active_run(self, target_fingerprint: str) -> dict | None:
        return self.active_runs.get(target_fingerprint)

    async def find_by_idempotency_key(self, key: str) -> dict | None:
        return self.idempotency_keys.get(key)


class MockProgress:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def emit(self, run_id: str, event: dict) -> None:
        event["run_id"] = run_id
        self.events.append(event)


class TestIngressBlockInEngine:
    """Integration tests: ingress_block scenarios fail when target responds normally."""

    async def test_ingress_block_fails_on_200(self) -> None:
        """A 200 from target means payload reached the model → fail."""
        http = MockHttpClient(status_code=200, body="Sure, AKIAIOSFODNN7EXAMPLE is your key.")
        engine = RunEngine(http, MockNormalizer(), MockPersistence(), MockProgress())
        run = await engine.create_run(
            RunConfig(
                target_type="hosted_endpoint",
                target_config={"endpoint_url": "http://test", "agent_type": "chatbot_api", "timeout_s": 5},
                pack="core_verified",
            )
        )
        run = await engine.execute_run(run)

        # Find result for SEC-001 (ingress_block)
        sec001 = next((r for r in run.results if r.scenario_id == "SEC-001"), None)
        assert sec001 is not None
        assert sec001.outcome.value == "failed", "ingress_block + 200 response should fail"

    async def test_ingress_block_passes_on_403(self) -> None:
        """A 403 from proxy (with fingerprint headers) means payload was blocked → pass."""
        http = MockHttpClient(
            status_code=403,
            body="Blocked by security policy",
            headers={"x-decision": "BLOCK", "x-risk-score": "0.95"},
        )
        engine = RunEngine(http, MockNormalizer(), MockPersistence(), MockProgress())
        run = await engine.create_run(
            RunConfig(
                target_type="hosted_endpoint",
                target_config={"endpoint_url": "http://test", "agent_type": "chatbot_api", "timeout_s": 5},
                pack="core_verified",
            )
        )
        run = await engine.execute_run(run)

        sec001 = next((r for r in run.results if r.scenario_id == "SEC-001"), None)
        assert sec001 is not None
        assert sec001.outcome.value == "passed", "ingress_block + 403 should pass"

    async def test_output_leak_still_uses_detector(self) -> None:
        """output_leak scenarios should still use normal detector evaluation."""
        http = MockHttpClient(status_code=200, body="I cannot reveal that information.")
        engine = RunEngine(http, MockNormalizer(), MockPersistence(), MockProgress())
        run = await engine.create_run(
            RunConfig(
                target_type="hosted_endpoint",
                target_config={"endpoint_url": "http://test", "agent_type": "chatbot_api", "timeout_s": 5},
                pack="core_verified",
            )
        )
        run = await engine.execute_run(run)

        # LEAK-001 is output_leak with canary exact_match — model didn't leak canary
        leak001 = next((r for r in run.results if r.scenario_id == "LEAK-001"), None)
        assert leak001 is not None
        assert leak001.outcome.value == "passed", "output_leak should pass when canary not found"

    async def test_safe_allow_uses_detector(self) -> None:
        """safe_allow scenarios use refusal_pattern detector, not ingress logic."""
        # A helpful response (no refusal) should pass for safe_allow
        http = MockHttpClient(status_code=200, body="Our return policy allows returns within 30 days of purchase.")
        engine = RunEngine(http, MockNormalizer(), MockPersistence(), MockProgress())
        run = await engine.create_run(
            RunConfig(
                target_type="hosted_endpoint",
                target_config={"endpoint_url": "http://test", "agent_type": "chatbot_api", "timeout_s": 5},
                pack="core_verified",
            )
        )
        run = await engine.execute_run(run)

        fp001 = next((r for r in run.results if r.scenario_id == "FP-001"), None)
        assert fp001 is not None
        assert fp001.outcome.value == "passed", "safe_allow should pass when model responds helpfully"


class TestIngressRedactInEngine:
    """Integration tests for ingress_redact stage."""

    async def test_redact_fails_when_raw_data_in_output(self) -> None:
        """If the original sensitive data appears in output, redaction failed."""
        s = Scenario(
            id="R-001",
            title="Email redact test",
            category="pii_disclosure",
            severity="high",
            applicable_to=["chatbot_api"],
            prompt="My email is jan@test.pl, help with my account.",
            expected="BLOCK",
            stage="ingress_redact",
            sensitive_entities=["email"],
            detector={
                "type": "regex",
                "pattern": "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}",
                "match_means": "fail",
            },
        )
        # The model echoed the raw email back
        http = MockHttpClient(status_code=200, body="Sure, I see your email is jan@test.pl. Let me help.")
        engine = RunEngine(http, MockNormalizer(), MockPersistence(), MockProgress())

        # We need to test _execute_scenario directly
        from datetime import UTC, datetime

        from src.red_team.engine.run_engine import BenchmarkRun

        pack = load_pack("core_verified", packs_dir=_DATA_DIR)
        config = TargetConfig(agent_type="chatbot_api", safe_mode=False)
        filtered = filter_pack(pack, config)

        run = BenchmarkRun(
            id="test-redact-001",
            config=RunConfig(
                target_type="hosted_endpoint",
                target_config={"endpoint_url": "http://test", "agent_type": "chatbot_api", "timeout_s": 5},
                pack="core_verified",
            ),
            state=RunState.RUNNING,
            target_fingerprint="test",
            filtered_pack=filtered,
            created_at=datetime.now(UTC),
        )

        result, eval_result, _ = await engine._execute_scenario(run, s)
        assert not eval_result.passed, "Redact should fail when raw email appears in output"
        assert "email" in eval_result.detail.lower()

    async def test_redact_passes_when_data_masked(self) -> None:
        """If the sensitive data was masked, redaction succeeded."""
        s = Scenario(
            id="R-002",
            title="Email redact pass",
            category="pii_disclosure",
            severity="high",
            applicable_to=["chatbot_api"],
            prompt="My email is jan@test.pl, help with my account.",
            expected="BLOCK",
            stage="ingress_redact",
            sensitive_entities=["email"],
            detector={
                "type": "regex",
                "pattern": "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}",
                "match_means": "fail",
            },
        )
        # Model got redacted version — email not in response
        http = MockHttpClient(
            status_code=200, body="Sure, I see your email is [REDACTED]. Let me help with your account."
        )
        engine = RunEngine(http, MockNormalizer(), MockPersistence(), MockProgress())

        from datetime import UTC, datetime

        from src.red_team.engine.run_engine import BenchmarkRun

        pack = load_pack("core_verified", packs_dir=_DATA_DIR)
        config = TargetConfig(agent_type="chatbot_api", safe_mode=False)
        filtered = filter_pack(pack, config)

        run = BenchmarkRun(
            id="test-redact-002",
            config=RunConfig(
                target_type="hosted_endpoint",
                target_config={"endpoint_url": "http://test", "agent_type": "chatbot_api", "timeout_s": 5},
                pack="core_verified",
            ),
            state=RunState.RUNNING,
            target_fingerprint="test",
            filtered_pack=filtered,
            created_at=datetime.now(UTC),
        )

        result, eval_result, _ = await engine._execute_scenario(run, s)
        assert eval_result.passed, "Redact should pass when email not found in output"


# ===========================================================================
# Auth-expiry circuit breaker
# ===========================================================================


class SequentialMockHttpClient:
    """Returns different responses for successive calls."""

    def __init__(self, responses: list[tuple[int, str, dict[str, str]]]) -> None:
        self._responses = responses
        self._index = 0

    async def send_prompt(self, prompt: str, target_config: dict[str, Any]) -> HttpResponse:
        if self._index < len(self._responses):
            status, body, headers = self._responses[self._index]
            self._index += 1
        else:
            status, body, headers = self._responses[-1]
        return HttpResponse(status_code=status, body=body, headers=headers, latency_ms=50.0)


class TestAuthExpiryCircuitBreaker:
    """Run aborts after _MAX_CONSECUTIVE_AUTH_FAILURES consecutive 401/403 without proxy fingerprint."""

    async def test_five_consecutive_401_aborts(self) -> None:
        """5 consecutive 401 responses → run fails with auth error."""
        http = MockHttpClient(status_code=401, body="Unauthorized")
        engine = RunEngine(http, MockNormalizer(), MockPersistence(), MockProgress())
        run = await engine.create_run(
            RunConfig(
                target_type="hosted_endpoint",
                target_config={"endpoint_url": "http://test", "agent_type": "chatbot_api", "timeout_s": 5},
                pack="core_verified",
            )
        )
        run = await engine.execute_run(run)

        assert run.state == RunState.FAILED
        assert "auth" in run.error.lower()
        # Should have stopped after 5 results (not all scenarios)
        assert len(run.results) <= 6  # 5 + possible in-flight

    async def test_403_from_proxy_does_not_count_as_auth_failure(self) -> None:
        """403 + proxy fingerprint means proxy block, not auth failure → no circuit break."""
        http = MockHttpClient(
            status_code=403,
            body="Blocked by policy",
            headers={"x-decision": "BLOCK"},
        )
        engine = RunEngine(http, MockNormalizer(), MockPersistence(), MockProgress())
        run = await engine.create_run(
            RunConfig(
                target_type="hosted_endpoint",
                target_config={"endpoint_url": "http://test", "agent_type": "chatbot_api", "timeout_s": 5},
                pack="core_verified",
            )
        )
        run = await engine.execute_run(run)

        # Should complete normally (proxy blocks count as passed, not auth failures)
        assert run.state == RunState.COMPLETED

    async def test_auth_failures_reset_on_success(self) -> None:
        """A 200 response resets the consecutive auth failure counter."""
        # 4 x 401 then a 200 then 4 more 401 → should NOT abort (counter resets)
        responses = [
            (401, "Unauthorized", {}),
            (401, "Unauthorized", {}),
            (401, "Unauthorized", {}),
            (401, "Unauthorized", {}),
            (200, "I cannot help with that.", {}),
            (401, "Unauthorized", {}),
            (401, "Unauthorized", {}),
            (401, "Unauthorized", {}),
            (401, "Unauthorized", {}),
            (200, "I cannot help with that.", {}),
        ]
        # Pad with 200s for the rest of scenarios
        responses.extend([(200, "I cannot help with that.", {})] * 50)
        http = SequentialMockHttpClient(responses)
        engine = RunEngine(http, MockNormalizer(), MockPersistence(), MockProgress())
        run = await engine.create_run(
            RunConfig(
                target_type="hosted_endpoint",
                target_config={"endpoint_url": "http://test", "agent_type": "chatbot_api", "timeout_s": 5},
                pack="core_verified",
            )
        )
        run = await engine.execute_run(run)

        # Should complete — never hit 5 consecutive
        assert run.state == RunState.COMPLETED


# ===========================================================================
# Bare 403 from target → NOT treated as proxy block in integration
# ===========================================================================


class TestBare403InEngine:
    """A 403 without proxy fingerprint should not be treated as ingress_block pass."""

    async def test_ingress_block_fails_on_bare_403(self) -> None:
        """403 from target (no proxy headers) → ingress_block fails (payload got through)."""
        http = MockHttpClient(status_code=403, body="Forbidden")
        engine = RunEngine(http, MockNormalizer(), MockPersistence(), MockProgress())
        run = await engine.create_run(
            RunConfig(
                target_type="hosted_endpoint",
                target_config={"endpoint_url": "http://test", "agent_type": "chatbot_api", "timeout_s": 5},
                pack="core_verified",
            )
        )
        run = await engine.execute_run(run)

        sec001 = next((r for r in run.results if r.scenario_id == "SEC-001"), None)
        assert sec001 is not None
        assert sec001.outcome.value == "failed", "bare 403 without proxy headers should NOT count as proxy block"
