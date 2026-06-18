"""Tests for the reproducibility manifest (build + verify round-trip + drift)."""

from __future__ import annotations

from src.red_team.manifest import build_manifest, scenario_set_hash, verify_manifest
from src.red_team.packs import TargetConfig
from src.red_team.packs.loader import clear_cache, resolve_filtered_pack

_CFG = TargetConfig(agent_type="chatbot_api")


def _selection_config(**sel) -> dict:
    return {"agent_type": "chatbot_api", "safe_mode": False, "selection": sel}


class TestBuildManifest:
    def test_selection_manifest_shape(self) -> None:
        clear_cache()
        cfg = _selection_config(packs=["promptfoo"], categories=["pii_disclosure"], subcategories=["api-db", "session"])
        filtered = resolve_filtered_pack("selection", cfg, _CFG)
        m = build_manifest("selection", cfg, filtered)
        assert m["mode"] == "selection"
        assert m["selection"]["packs"] == ["promptfoo"]
        assert m["selection"]["subcategories"] == ["api-db", "session"]
        assert m["packs"][0]["name"] == "promptfoo" and m["packs"][0]["version"]
        assert m["scenario_count"] == len(filtered.scenarios)
        assert m["scenario_ids"] == [s.id for s in filtered.scenarios]
        assert m["scenario_set_hash"].startswith("sha256:")
        assert m["grader"]["type"] == "deterministic"

    def test_hash_is_order_independent(self) -> None:
        clear_cache()
        cfg = _selection_config(packs=["promptfoo"], categories=["pii_disclosure"])
        filtered = resolve_filtered_pack("selection", cfg, _CFG)
        h1 = scenario_set_hash(filtered.scenarios)
        h2 = scenario_set_hash(list(reversed(filtered.scenarios)))
        assert h1 == h2  # sorted by id internally


class TestVerifyRoundTrip:
    def test_selection_round_trips_reproducible(self) -> None:
        clear_cache()
        cfg = _selection_config(packs=["promptfoo"], categories=["pii_disclosure"], subcategories=["api-db"])
        filtered = resolve_filtered_pack("selection", cfg, _CFG)
        m = build_manifest("selection", cfg, filtered)
        res = verify_manifest(m)
        assert res["reproducible"] is True
        assert res["actual_hash"] == res["expected_hash"]
        assert res["actual_count"] == res["expected_count"]

    def test_sampled_selection_round_trips(self) -> None:
        # Seeded sampling must reproduce the exact subset on verify.
        clear_cache()
        cfg = _selection_config(packs=["promptfoo"], categories=["pii_disclosure"], sample_per_category=5, seed=99)
        filtered = resolve_filtered_pack("selection", cfg, _CFG)
        m = build_manifest("selection", cfg, filtered)
        assert m["scenario_count"] <= 5
        assert verify_manifest(m)["reproducible"] is True

    def test_single_pack_round_trips(self) -> None:
        clear_cache()
        filtered = resolve_filtered_pack("core_security", {}, _CFG)
        m = build_manifest("core_security", {}, filtered)
        assert m["mode"] == "single"
        assert verify_manifest(m)["reproducible"] is True

    def test_drift_is_detected(self) -> None:
        clear_cache()
        cfg = _selection_config(packs=["promptfoo"], categories=["pii_disclosure"])
        filtered = resolve_filtered_pack("selection", cfg, _CFG)
        m = build_manifest("selection", cfg, filtered)
        m["scenario_set_hash"] = "sha256:deadbeef"  # simulate corpus drift
        res = verify_manifest(m)
        assert res["reproducible"] is False
        assert res["actual_hash"] != res["expected_hash"]
