"""Red Team API — Pydantic request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateRunRequest(BaseModel):
    """POST /v1/benchmark/runs body."""

    target_type: str = Field(..., examples=["demo"])
    target_config: dict[str, Any] = Field(default_factory=dict)
    pack: str = Field(..., examples=["core_security"])
    policy: str | None = None
    source_run_id: str | None = None
    idempotency_key: str | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class RunCreatedResponse(BaseModel):
    """Returned from POST /v1/benchmark/runs."""

    id: uuid.UUID
    status: str
    pack: str
    total_in_pack: int
    total_applicable: int


class RunSummary(BaseModel):
    """Item in the list-runs response."""

    id: uuid.UUID
    target_type: str
    pack: str
    status: str
    score_simple: int | None = None
    score_weighted: int | None = None
    confidence: str | None = None
    total_in_pack: int = 0
    total_applicable: int = 0
    executed: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    protection_detected: bool = False
    proxy_blocked_count: int = 0
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class RunDetailResponse(RunSummary):
    """Returned from GET /v1/benchmark/runs/:id — includes all fields."""

    target_config: dict[str, Any] = Field(default_factory=dict)
    target_fingerprint: str = ""
    pack_version: str | None = None
    policy: str | None = None
    skipped_reasons: dict[str, int] = Field(default_factory=dict)
    false_positives: int = 0
    source_run_id: uuid.UUID | None = None
    idempotency_key: uuid.UUID | None = None
    error: str | None = None


class ScenarioResultResponse(BaseModel):
    """Single scenario result (list and detail views)."""

    id: uuid.UUID
    scenario_id: str
    category: str
    severity: str
    prompt: str
    expected: str
    actual: str | None = None
    passed: bool | None = None
    skipped: bool = False
    skipped_reason: str | None = None
    detector_type: str | None = None
    detector_detail: dict | None = None
    latency_ms: int | None = None
    raw_response_body: str | None = None
    pipeline_result: dict | None = None
    created_at: datetime | None = None

    # Enriched from pack metadata (not stored in DB)
    title: str | None = None
    description: str | None = None
    why_it_passes: str | None = None
    fix_hints: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PackInfoResponse(BaseModel):
    """Available pack metadata."""

    name: str
    display_name: str
    description: str
    version: str
    scenario_count: int
    applicable_to: list[str]


class CompareResponse(BaseModel):
    """Diff between two benchmark runs."""

    run_a_id: uuid.UUID
    run_b_id: uuid.UUID
    score_delta: int
    weighted_delta: int
    warning: str | None = None
    run_a: RunSummary
    run_b: RunSummary
    fixed_failures: list[str] = Field(default_factory=list)
    new_failures: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Test-connection schemas
# ---------------------------------------------------------------------------


class TestConnectionRequest(BaseModel):
    """POST /v1/benchmark/test-connection body."""

    endpoint_url: str
    auth_header: str | None = None
    timeout_s: int = Field(default=10, ge=1, le=120)


class TestConnectionResponse(BaseModel):
    """Result of a target connectivity check."""

    status: str  # "ok" | "error"
    status_code: int | None = None
    latency_ms: int | None = None
    content_type: str | None = None
    error: str | None = None
    error_code: str | None = None  # "connection_failed" | "auth_invalid" | "timeout" | "ssl_error"
    resolved_url: str | None = None  # actual URL used (after localhost rewrite)


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str


class StructuredError(BaseModel):
    """Structured error with code and optional details."""

    code: str  # e.g. "connection_failed", "auth_invalid", "timeout", etc.
    message: str
    details: dict[str, Any] | None = None


class StructuredErrorResponse(BaseModel):
    """Wraps a structured error for API responses."""

    error: StructuredError
