"""Prove ISS-001 fix: LLM Guard scanners rebuild when thresholds change."""

from src.pipeline.nodes.llm_guard import get_scanners, reset_scanners


class TestHotReload:
    def setup_method(self):
        reset_scanners()

    def teardown_method(self):
        reset_scanners()

    def test_same_thresholds_return_cached_object(self):
        th = {"injection_threshold": 0.5, "toxicity_threshold": 0.7}
        s1 = get_scanners(th)
        s2 = get_scanners(th)
        assert s1 is s2, "Same thresholds should return the cached list"

    def test_different_thresholds_rebuild_scanners(self):
        th1 = {"injection_threshold": 0.5, "toxicity_threshold": 0.7}
        th2 = {"injection_threshold": 0.3, "toxicity_threshold": 0.9}
        s1 = get_scanners(th1)
        s2 = get_scanners(th2)
        assert s1 is not s2, "Changed thresholds must rebuild scanners"

    def test_rebuilt_scanners_use_new_threshold(self):
        th1 = {"injection_threshold": 0.5, "toxicity_threshold": 0.7}
        th2 = {"injection_threshold": 0.3, "toxicity_threshold": 0.9}
        get_scanners(th1)
        s2 = get_scanners(th2)
        pi = s2[0]  # PromptInjection is first
        assert pi._threshold == 0.3, f"Expected 0.3, got {pi._threshold}"

    def test_revert_to_original_thresholds_rebuilds(self):
        th1 = {"injection_threshold": 0.5, "toxicity_threshold": 0.7}
        th2 = {"injection_threshold": 0.3, "toxicity_threshold": 0.9}
        s1 = get_scanners(th1)
        get_scanners(th2)
        s3 = get_scanners(th1)
        assert s1 is not s3, "Reverting thresholds should rebuild (not reuse stale)"

    def test_only_injection_change_triggers_rebuild(self):
        th1 = {"injection_threshold": 0.5, "toxicity_threshold": 0.7}
        th2 = {"injection_threshold": 0.6, "toxicity_threshold": 0.7}
        s1 = get_scanners(th1)
        s2 = get_scanners(th2)
        assert s1 is not s2, "Changing only injection_threshold should rebuild"

    def test_only_toxicity_change_triggers_rebuild(self):
        th1 = {"injection_threshold": 0.5, "toxicity_threshold": 0.7}
        th2 = {"injection_threshold": 0.5, "toxicity_threshold": 0.8}
        s1 = get_scanners(th1)
        s2 = get_scanners(th2)
        assert s1 is not s2, "Changing only toxicity_threshold should rebuild"

    def test_irrelevant_threshold_does_not_rebuild(self):
        th1 = {"injection_threshold": 0.5, "toxicity_threshold": 0.7, "nemo_weight": 0.3}
        th2 = {"injection_threshold": 0.5, "toxicity_threshold": 0.7, "nemo_weight": 0.9}
        s1 = get_scanners(th1)
        s2 = get_scanners(th2)
        assert s1 is s2, "Changing unrelated keys should NOT rebuild"
