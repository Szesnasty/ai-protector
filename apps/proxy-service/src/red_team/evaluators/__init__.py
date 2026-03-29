"""Evaluator Engine — pure-function detector layer.

Public API:
    evaluate_scenario(scenario, response) → EvalResult
    Registry: register_detector, get_detector, is_available, list_available
    Detectors: exact_match, regex_detector, keyword_detector, refusal_pattern,
               json_assertion, tool_call_detect, heuristic_detector
"""

from src.red_team.evaluators.detectors import (
    exact_match,
    heuristic_detector,
    json_assertion,
    keyword_detector,
    refusal_pattern,
    regex_detector,
    tool_call_detect,
)
from src.red_team.evaluators.registry import (
    get_detector,
    is_available,
    list_available,
    register_detector,
)
from src.red_team.schemas import Scenario
from src.red_team.schemas.dataclasses import EvalResult, RawTargetResponse
from src.red_team.schemas.enums import DetectorType

# ---------------------------------------------------------------------------
# Register all MVP detectors
# ---------------------------------------------------------------------------

register_detector(DetectorType.EXACT_MATCH.value, exact_match)
register_detector(DetectorType.REGEX.value, regex_detector)
register_detector(DetectorType.KEYWORD.value, keyword_detector)
register_detector(DetectorType.REFUSAL_PATTERN.value, refusal_pattern)
register_detector(DetectorType.JSON_ASSERTION.value, json_assertion)
register_detector(DetectorType.TOOL_CALL_DETECT.value, tool_call_detect)
register_detector(DetectorType.HEURISTIC.value, heuristic_detector)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def evaluate_scenario(scenario: Scenario, response: RawTargetResponse) -> EvalResult:
    """Evaluate a single scenario against a target response.

    Looks up the detector by scenario.detector.type and calls it.
    """
    detector_type = scenario.detector.type
    if isinstance(detector_type, DetectorType):
        detector_type = detector_type.value

    fn = get_detector(detector_type)
    if fn is None:
        return EvalResult(
            passed=False,
            confidence=0.0,
            detail=f"No detector registered for type: {detector_type}",
            detector_type=detector_type,
            matched_evidence=None,
        )

    return fn(scenario.detector, response)


__all__ = [
    # Convenience
    "evaluate_scenario",
    # Registry
    "get_detector",
    "is_available",
    "list_available",
    "register_detector",
    # Detectors
    "exact_match",
    "heuristic_detector",
    "json_assertion",
    "keyword_detector",
    "refusal_pattern",
    "regex_detector",
    "tool_call_detect",
]
