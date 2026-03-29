"""Pydantic models for scenario schema and pack validation.

No I/O, no side effects — pure data validation.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from src.red_team.schemas.enums import AgentType, Category, DetectorType, ExpectedAction, ScenarioStage, Severity

# ---------------------------------------------------------------------------
# Per-detector config schemas
# ---------------------------------------------------------------------------


class RegexDetectorConfig(BaseModel):
    type: Literal[DetectorType.REGEX] = DetectorType.REGEX
    pattern: str
    match_means: Literal["fail", "pass"] = "fail"


class KeywordDetectorConfig(BaseModel):
    type: Literal[DetectorType.KEYWORD] = DetectorType.KEYWORD
    keywords: list[str] = Field(min_length=1)
    match_means: Literal["fail", "pass"] = "fail"
    case_sensitive: bool = False


class RefusalPatternConfig(BaseModel):
    type: Literal[DetectorType.REFUSAL_PATTERN] = DetectorType.REFUSAL_PATTERN
    refusal_phrases: list[str] = Field(min_length=1)
    min_match: int = 1
    match_means: Literal["fail", "pass"] = "pass"


class JsonAssertionFieldCheck(BaseModel):
    """A single field-level assertion for multi-assertion json_assertion mode."""

    field: str
    operator: Literal["equals", "contains", "not_equals"] = "equals"
    value: str


class JsonAssertionConfig(BaseModel):
    type: Literal[DetectorType.JSON_ASSERTION] = DetectorType.JSON_ASSERTION
    # Legacy single-field mode
    path: str | None = None  # JSONPath expression, e.g. "$.decision"
    expected: str | None = None
    # Multi-assertion mode
    mode: Literal["fail_if_any", "pass_if_all"] | None = None
    assertions: list[JsonAssertionFieldCheck] | None = None
    # Text fallback: if structured output unavailable, check body_text for this
    fallback_forbidden_string: str | None = None


class ToolCallDetectConfig(BaseModel):
    type: Literal[DetectorType.TOOL_CALL_DETECT] = DetectorType.TOOL_CALL_DETECT
    tool_names: list[str] = Field(min_length=1)
    invoked_means: Literal["fail", "pass"] = "fail"


class ExactMatchConfig(BaseModel):
    type: Literal[DetectorType.EXACT_MATCH] = DetectorType.EXACT_MATCH
    forbidden_strings: list[str] = Field(min_length=1)
    match_means: Literal["fail", "pass"] = "fail"
    case_sensitive: bool = True


class HeuristicConfig(BaseModel):
    type: Literal[DetectorType.HEURISTIC] = DetectorType.HEURISTIC
    checks: list[str] = Field(min_length=1)
    fail_threshold: int = 2


class LlmJudgeConfig(BaseModel):
    type: Literal[DetectorType.LLM_JUDGE] = DetectorType.LLM_JUDGE
    judge_prompt: str
    fail_on: str = "YES"


# Discriminated union of all detector configs
DetectorConfig = Annotated[
    RegexDetectorConfig
    | KeywordDetectorConfig
    | RefusalPatternConfig
    | JsonAssertionConfig
    | ToolCallDetectConfig
    | ExactMatchConfig
    | HeuristicConfig
    | LlmJudgeConfig,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Scenario model
# ---------------------------------------------------------------------------


class Scenario(BaseModel):
    """A single attack scenario within a pack."""

    id: str
    title: str
    category: Category
    severity: Severity
    mutating: bool = False
    applicable_to: list[AgentType] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    prompt: str = Field(min_length=1)
    expected: ExpectedAction

    # Stage classification — determines evaluation strategy
    stage: ScenarioStage = ScenarioStage.OUTPUT_LEAK
    sensitive_entities: list[str] = Field(default_factory=list)  # e.g. ["pesel", "email"]

    detector: DetectorConfig

    fix_hints: list[str] = Field(default_factory=list)
    description: str = ""
    why_it_passes: str | None = None

    pack_version: str | None = None  # Set at load time from the pack header


# ---------------------------------------------------------------------------
# Pack model
# ---------------------------------------------------------------------------


class Pack(BaseModel):
    """An attack-scenario pack (e.g. core_security.yaml)."""

    name: str
    version: str
    description: str = ""
    scenario_count: int = Field(ge=0)
    applicable_to: list[AgentType] = Field(min_length=1)
    system_prompt: str | None = None  # Injected into target as system message; supports ${CANARY}
    scenarios: list[Scenario]

    @model_validator(mode="after")
    def _validate_pack_invariants(self) -> Pack:
        # scenario_count must match actual count
        if self.scenario_count != len(self.scenarios):
            raise ValueError(f"scenario_count ({self.scenario_count}) != actual scenarios ({len(self.scenarios)})")

        # All scenario IDs must be unique
        seen_ids: set[str] = set()
        for s in self.scenarios:
            if s.id in seen_ids:
                raise ValueError(f"Duplicate scenario id: {s.id}")
            seen_ids.add(s.id)

        # Pack applicable_to must be superset of each scenario's applicable_to
        pack_types = set(self.applicable_to)
        for s in self.scenarios:
            scenario_types = set(s.applicable_to)
            if not scenario_types.issubset(pack_types):
                raise ValueError(
                    f"Scenario {s.id} applicable_to {scenario_types} is not a subset of pack applicable_to {pack_types}"
                )

        return self
