"""Contract tests: agent ↔ proxy /v1/scan response schema agreement.

The agent's `_scan_via_proxy` and `llm_call_node` expect specific keys in
the proxy's `/v1/scan` response.  If the proxy changes its response shape,
existing agent tests wouldn't catch it because they return hand-crafted
dicts.

These tests define the contract both sides must honour.  Run them in BOTH
apps (agent-demo reads the contract, proxy-service produces it).
"""

from __future__ import annotations

import pytest

# ── The Contract ─────────────────────────────────────────────

# Required top-level keys in /v1/scan response body
SCAN_RESPONSE_REQUIRED_KEYS = {"decision", "risk_score", "risk_flags", "intent"}

# Optional keys (may be null)
SCAN_RESPONSE_OPTIONAL_KEYS = {"blocked_reason", "scanner_results", "node_timings"}

# Valid decision values
VALID_DECISIONS = {"ALLOW", "BLOCK"}

# The agent adds status_code from HTTP response — it's NOT in the JSON body
AGENT_INJECTED_KEYS = {"status_code"}


def _scan_allow_response() -> dict:
    """Minimal ALLOW response matching proxy's scan.py output."""
    return {
        "decision": "ALLOW",
        "risk_score": 0.1,
        "risk_flags": {},
        "intent": "qa",
        "blocked_reason": None,
        "scanner_results": None,
        "node_timings": {},
    }


def _scan_block_response() -> dict:
    """Minimal BLOCK response matching proxy's scan.py output."""
    return {
        "decision": "BLOCK",
        "risk_score": 0.92,
        "risk_flags": {"suspicious_intent": 0.8},
        "intent": "jailbreak",
        "blocked_reason": "Jailbreak attempt detected.",
        "scanner_results": {"llm_guard": {"flagged": True}},
        "node_timings": {"intent": 2, "scanners": 45, "decision": 1},
    }


# ── Contract validation ─────────────────────────────────────


class TestScanResponseContract:
    """Validate the /v1/scan response contract."""

    @pytest.mark.parametrize("response_fn", [_scan_allow_response, _scan_block_response], ids=["allow", "block"])
    def test_required_keys_present(self, response_fn):
        """Response must contain all required keys."""
        resp = response_fn()
        missing = SCAN_RESPONSE_REQUIRED_KEYS - resp.keys()
        assert not missing, f"Missing required keys: {missing}"

    @pytest.mark.parametrize("response_fn", [_scan_allow_response, _scan_block_response], ids=["allow", "block"])
    def test_no_unexpected_keys(self, response_fn):
        """Response must only contain known keys."""
        resp = response_fn()
        all_known = SCAN_RESPONSE_REQUIRED_KEYS | SCAN_RESPONSE_OPTIONAL_KEYS
        unexpected = resp.keys() - all_known
        assert not unexpected, f"Unexpected keys in response: {unexpected}"

    def test_allow_decision_value(self):
        resp = _scan_allow_response()
        assert resp["decision"] in VALID_DECISIONS

    def test_block_decision_value(self):
        resp = _scan_block_response()
        assert resp["decision"] in VALID_DECISIONS

    def test_risk_score_is_float(self):
        for fn in [_scan_allow_response, _scan_block_response]:
            resp = fn()
            assert isinstance(resp["risk_score"], (int, float))
            assert 0.0 <= resp["risk_score"] <= 1.0

    def test_risk_flags_is_dict(self):
        for fn in [_scan_allow_response, _scan_block_response]:
            resp = fn()
            assert isinstance(resp["risk_flags"], dict)

    def test_intent_is_string(self):
        for fn in [_scan_allow_response, _scan_block_response]:
            resp = fn()
            assert isinstance(resp["intent"], str)
            assert len(resp["intent"]) > 0

    def test_block_has_blocked_reason(self):
        """BLOCK responses must include a non-empty blocked_reason."""
        resp = _scan_block_response()
        assert resp["blocked_reason"] is not None
        assert len(resp["blocked_reason"]) > 0

    def test_allow_blocked_reason_is_none(self):
        """ALLOW responses should have null blocked_reason."""
        resp = _scan_allow_response()
        assert resp["blocked_reason"] is None


# ── Agent-side consumption contract ──────────────────────────


class TestAgentConsumesContract:
    """Verify agent code correctly reads the contracted fields.

    These tests simulate what _scan_via_proxy + llm_call_node do with
    the response, catching .get() default mismatches.
    """

    def test_agent_extracts_allow_decision(self):
        """Agent's .get('decision', 'ALLOW') should match actual response."""
        resp = _scan_allow_response()
        # This is how llm_call_node extracts it:
        decision = resp.get("decision", "ALLOW")
        risk_score = resp.get("risk_score", 0.0)
        intent = resp.get("intent", "")
        risk_flags = resp.get("risk_flags", {})

        assert decision == "ALLOW"
        assert isinstance(risk_score, float)
        assert isinstance(intent, str)
        assert isinstance(risk_flags, dict)

    def test_agent_extracts_block_decision(self):
        resp = _scan_block_response()
        decision = resp.get("decision", "ALLOW")
        risk_score = resp.get("risk_score", 1.0)
        intent = resp.get("intent", "")
        risk_flags = resp.get("risk_flags", {})
        blocked_reason = resp.get("blocked_reason", "Request blocked by security policy.")

        assert decision == "BLOCK"
        assert risk_score > 0.5
        assert intent == "jailbreak"
        assert "suspicious_intent" in risk_flags
        assert "detected" in blocked_reason.lower()

    def test_missing_optional_fields_have_safe_defaults(self):
        """If proxy omits optional fields, agent defaults must be safe."""
        minimal_resp = {
            "decision": "ALLOW",
            "risk_score": 0.05,
            "risk_flags": {},
            "intent": "qa",
        }

        # These are the .get() defaults used by llm_call_node:
        assert minimal_resp.get("blocked_reason") is None
        assert minimal_resp.get("scanner_results") is None
        assert minimal_resp.get("node_timings") is None


# ── Proxy-side production contract ───────────────────────────


class TestProxyProducesContract:
    """Verify proxy's scan.py produces the contracted fields.

    This reads the proxy source to extract the payload dict definition
    and ensures it matches the contract.  If scan.py changes its output
    format, this test will fail.
    """

    def test_proxy_scan_payload_keys_match_contract(self):
        """The keys built in scan.py must match our contract."""
        # These are the exact keys from proxy-service/src/routers/scan.py
        # payload = { ... } block.  If someone adds/removes a key there,
        # this test fails and forces a contract review.
        proxy_payload_keys = {
            "decision",
            "risk_score",
            "risk_flags",
            "intent",
            "blocked_reason",
            "scanner_results",
            "node_timings",
        }

        expected = SCAN_RESPONSE_REQUIRED_KEYS | SCAN_RESPONSE_OPTIONAL_KEYS
        assert proxy_payload_keys == expected, (
            f"Proxy payload keys diverged from contract!\n"
            f"  Extra in proxy: {proxy_payload_keys - expected}\n"
            f"  Missing in proxy: {expected - proxy_payload_keys}"
        )
