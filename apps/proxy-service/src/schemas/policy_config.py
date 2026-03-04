"""Pydantic validation schema for the JSONB ``config`` field in Policy."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Node names that may appear in the policy ``nodes`` list.
# Core pipeline nodes (parse, intent, rules, decision, transform, llm) always
# run and should NOT appear here — this set covers optional scanners / extensions.
VALID_NODES: frozenset[str] = frozenset({
    # Scanners
    "llm_guard",
    "presidio",
    "nemo_guardrails",
    "ml_judge",
    # Output pipeline
    "output_filter",
    "memory_hygiene",
    "logging",
    # Extensions
    "canary",
})


class ThresholdsSchema(BaseModel):
    """Threshold / behaviour knobs inside a policy config."""

    max_risk: float = Field(0.7, ge=0.0, le=1.0)
    injection_threshold: float = Field(0.5, ge=0.0, le=1.0)
    toxicity_threshold: float = Field(0.7, ge=0.0, le=1.0)
    pii_action: Literal["flag", "mask", "block"] = "flag"
    enable_canary: bool = False

    # Risk-score weights (configurable per policy)
    injection_weight: float = Field(0.8, ge=0.0, le=1.0)
    toxicity_weight: float = Field(0.5, ge=0.0, le=1.0)
    secrets_weight: float = Field(0.6, ge=0.0, le=1.0)
    invisible_weight: float = Field(0.4, ge=0.0, le=1.0)
    pii_per_entity_weight: float = Field(0.1, ge=0.0, le=1.0)
    pii_max_weight: float = Field(0.5, ge=0.0, le=1.0)
    nemo_weight: float = Field(0.7, ge=0.0, le=1.0)


class PolicyConfigSchema(BaseModel):
    """Validates the JSONB ``config`` column of a policy.

    ``nodes`` — list of optional scanner / extension node names.
    ``thresholds`` — risk thresholds and behaviour toggles.
    """

    nodes: list[str] = Field(default_factory=list)
    thresholds: ThresholdsSchema = Field(default_factory=ThresholdsSchema)

    @field_validator("nodes")
    @classmethod
    def validate_nodes(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_NODES
        if invalid:
            raise ValueError(f"Invalid node names: {sorted(invalid)}")
        return v
