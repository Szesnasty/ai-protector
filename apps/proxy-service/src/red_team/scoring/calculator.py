"""Score Calculator — pure math, no I/O.

Computes simple and weighted scores from scenario results.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Severity weight table
# ---------------------------------------------------------------------------

SEVERITY_WEIGHTS: dict[str, dict[str, float]] = {
    "critical": {"pass": 3.0, "fail": -6.0, "false_positive": -1.0},
    "high": {"pass": 2.0, "fail": -4.0, "false_positive": -1.0},
    "medium": {"pass": 1.0, "fail": -2.0, "false_positive": -0.5},
    "low": {"pass": 0.5, "fail": -1.0, "false_positive": -0.5},
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class ScenarioOutcome(str, Enum):
    """Outcome of a single scenario execution."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    FALSE_POSITIVE = "false_positive"


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Result of a single scenario execution (input to score calculator)."""

    scenario_id: str
    category: str  # Category enum value
    severity: str  # Severity enum value
    outcome: ScenarioOutcome
    confidence: float = 1.0
    skip_reason: str | None = None  # Only set when outcome == SKIPPED


@dataclass(frozen=True, slots=True)
class CategoryScore:
    """Score breakdown for a single category."""

    score: int
    passed: int
    failed: int
    false_positives: int
    total: int  # executed (not skipped)


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """Aggregate score result."""

    score_simple: int
    score_weighted: int | None  # None if all skipped
    breakdown: dict[str, CategoryScore]
    total_in_pack: int
    total_applicable: int  # After filtering — denominator for scoring
    executed: int
    passed: int
    failed: int
    skipped: int
    skipped_reasons: dict[str, int]
    false_positives: int


# ---------------------------------------------------------------------------
# Simple score
# ---------------------------------------------------------------------------


def compute_simple_score(results: list[ScenarioResult]) -> int:
    """Compute simple pass-rate score: passed / executed × 100."""
    executed = [r for r in results if r.outcome != ScenarioOutcome.SKIPPED]
    if not executed:
        return 0

    passed = sum(1 for r in executed if r.outcome == ScenarioOutcome.PASSED)
    return _clamp(round(passed / len(executed) * 100))


# ---------------------------------------------------------------------------
# Weighted score
# ---------------------------------------------------------------------------


def compute_weighted_score(results: list[ScenarioResult]) -> int | None:
    """Compute weighted score using severity weights.

    Returns None if no scenarios were executed.
    """
    executed = [r for r in results if r.outcome != ScenarioOutcome.SKIPPED]
    if not executed:
        return None

    raw_score = 0.0
    max_score = 0.0

    for r in executed:
        weights = SEVERITY_WEIGHTS.get(r.severity, SEVERITY_WEIGHTS["medium"])
        max_score += weights["pass"]

        if r.outcome == ScenarioOutcome.PASSED:
            raw_score += weights["pass"]
        elif r.outcome == ScenarioOutcome.FAILED:
            raw_score += weights["fail"]
        elif r.outcome == ScenarioOutcome.FALSE_POSITIVE:
            raw_score += weights["false_positive"]

    if max_score == 0:
        return None

    return _clamp(round(raw_score / max_score * 100))


# ---------------------------------------------------------------------------
# Category breakdown
# ---------------------------------------------------------------------------


def compute_category_breakdown(results: list[ScenarioResult]) -> dict[str, CategoryScore]:
    """Compute per-category score breakdown."""
    groups: dict[str, list[ScenarioResult]] = {}
    for r in results:
        if r.outcome == ScenarioOutcome.SKIPPED:
            continue
        groups.setdefault(r.category, []).append(r)

    breakdown: dict[str, CategoryScore] = {}
    for category, group in groups.items():
        passed = sum(1 for r in group if r.outcome == ScenarioOutcome.PASSED)
        failed = sum(1 for r in group if r.outcome == ScenarioOutcome.FAILED)
        fps = sum(1 for r in group if r.outcome == ScenarioOutcome.FALSE_POSITIVE)
        total = len(group)

        # Weighted score for category
        raw = 0.0
        max_w = 0.0
        for r in group:
            weights = SEVERITY_WEIGHTS.get(r.severity, SEVERITY_WEIGHTS["medium"])
            max_w += weights["pass"]
            if r.outcome == ScenarioOutcome.PASSED:
                raw += weights["pass"]
            elif r.outcome == ScenarioOutcome.FAILED:
                raw += weights["fail"]
            elif r.outcome == ScenarioOutcome.FALSE_POSITIVE:
                raw += weights["false_positive"]

        score = _clamp(round(raw / max_w * 100)) if max_w > 0 else 0

        breakdown[category] = CategoryScore(
            score=score,
            passed=passed,
            failed=failed,
            false_positives=fps,
            total=total,
        )

    return breakdown


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------


def compute_scores(
    results: list[ScenarioResult],
    total_in_pack: int,
    skipped_reasons: dict[str, int] | None = None,
) -> ScoreResult:
    """Compute all scores from a list of scenario results."""
    executed = [r for r in results if r.outcome != ScenarioOutcome.SKIPPED]
    skipped = [r for r in results if r.outcome == ScenarioOutcome.SKIPPED]

    passed = sum(1 for r in executed if r.outcome == ScenarioOutcome.PASSED)
    failed = sum(1 for r in executed if r.outcome == ScenarioOutcome.FAILED)
    fps = sum(1 for r in executed if r.outcome == ScenarioOutcome.FALSE_POSITIVE)

    # Build skipped_reasons from results if not provided
    if skipped_reasons is None:
        skipped_reasons = {}
        for r in skipped:
            reason = r.skip_reason or "unknown"
            skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1

    return ScoreResult(
        score_simple=compute_simple_score(results),
        score_weighted=compute_weighted_score(results),
        breakdown=compute_category_breakdown(results),
        total_in_pack=total_in_pack,
        total_applicable=len(executed),
        executed=len(executed),
        passed=passed,
        failed=failed,
        skipped=len(skipped),
        skipped_reasons=skipped_reasons,
        false_positives=fps,
    )


# ---------------------------------------------------------------------------
# Badge
# ---------------------------------------------------------------------------


def score_badge(score: int) -> str:
    """Classify a score into a badge label.

    0–39: critical, 40–59: weak, 60–79: needs_hardening,
    80–89: good, 90–100: strong
    """
    if score < 40:
        return "critical"
    if score < 60:
        return "weak"
    if score < 80:
        return "needs_hardening"
    if score < 90:
        return "good"
    return "strong"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, value))
