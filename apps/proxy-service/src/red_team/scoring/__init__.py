"""Score Calculator — pure math, no I/O.

Public API:
    compute_simple_score(results) → int
    compute_weighted_score(results) → int | None
    compute_category_breakdown(results) → dict[str, CategoryScore]
    compute_scores(results, total_in_pack) → ScoreResult
    score_badge(score) → str
    Dataclasses: ScenarioResult, ScenarioOutcome, CategoryScore, ScoreResult
"""

from src.red_team.scoring.calculator import (
    SEVERITY_WEIGHTS,
    CategoryScore,
    ScenarioOutcome,
    ScenarioResult,
    ScoreResult,
    compute_category_breakdown,
    compute_scores,
    compute_simple_score,
    compute_weighted_score,
    score_badge,
)

__all__ = [
    "SEVERITY_WEIGHTS",
    "CategoryScore",
    "ScenarioOutcome",
    "ScenarioResult",
    "ScoreResult",
    "compute_category_breakdown",
    "compute_scores",
    "compute_simple_score",
    "compute_weighted_score",
    "score_badge",
]
