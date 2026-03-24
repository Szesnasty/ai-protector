"""Scenario Schema — pure data validation, zero I/O.

Public API:
    Enums: DetectorType, Severity, ExpectedAction, AgentType, Category
    Models: Scenario, Pack, DetectorConfig, and per-detector configs
    Dataclasses: RawTargetResponse, ToolCall, EvalResult
"""

from src.red_team.schemas.dataclasses import EvalResult, RawTargetResponse, ToolCall
from src.red_team.schemas.enums import AgentType, Category, DetectorType, ExpectedAction, Severity
from src.red_team.schemas.models import (
    DetectorConfig,
    ExactMatchConfig,
    HeuristicConfig,
    JsonAssertionConfig,
    KeywordDetectorConfig,
    Pack,
    RefusalPatternConfig,
    RegexDetectorConfig,
    Scenario,
    ToolCallDetectConfig,
)

__all__ = [
    # Enums
    "AgentType",
    "Category",
    "DetectorType",
    "ExpectedAction",
    "Severity",
    # Pydantic models
    "DetectorConfig",
    "ExactMatchConfig",
    "HeuristicConfig",
    "JsonAssertionConfig",
    "KeywordDetectorConfig",
    "Pack",
    "RefusalPatternConfig",
    "RegexDetectorConfig",
    "Scenario",
    "ToolCallDetectConfig",
    # Dataclasses
    "EvalResult",
    "RawTargetResponse",
    "ToolCall",
]
