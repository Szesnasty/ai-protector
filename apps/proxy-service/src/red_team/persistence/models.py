"""SQLAlchemy models for Red Team benchmark persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class BenchmarkRun(UUIDMixin, TimestampMixin, Base):
    """A single Red Team benchmark run."""

    __tablename__ = "benchmark_runs"
    __table_args__ = (
        Index("ix_benchmark_runs_status", "status"),
        Index("ix_benchmark_runs_target_fingerprint", "target_fingerprint"),
        Index(
            "ix_benchmark_runs_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where="idempotency_key IS NOT NULL",
        ),
    )

    # ── Target ───────────────────────────────────────────────────────
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    target_fingerprint: Mapped[str] = mapped_column(String(16), nullable=False)

    # ── Pack ─────────────────────────────────────────────────────────
    pack: Mapped[str] = mapped_column(String(64), nullable=False)
    pack_version: Mapped[str] = mapped_column(String(32), nullable=True)
    policy: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # ── Status ───────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")

    # ── Scores ───────────────────────────────────────────────────────
    score_simple: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_weighted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # ── Counting ─────────────────────────────────────────────────────
    total_in_pack: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_applicable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    executed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_reasons: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    false_positives: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Re-run & idempotency ─────────────────────────────────────────
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("benchmark_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    # ── Protection detection ─────────────────────────────────────────
    protection_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    proxy_blocked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # ── Timestamps ───────────────────────────────────────────────────
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ────────────────────────────────────────────────
    scenario_results: Mapped[list[BenchmarkScenarioResult]] = relationship(
        back_populates="run",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    source_run: Mapped[BenchmarkRun | None] = relationship(
        remote_side="BenchmarkRun.id",
        lazy="selectin",
    )


class BenchmarkScenarioResult(UUIDMixin, TimestampMixin, Base):
    """Result of a single scenario within a benchmark run."""

    __tablename__ = "benchmark_scenario_results"
    __table_args__ = (
        Index("ix_benchmark_scenario_results_run_id", "run_id"),
        Index("ix_benchmark_scenario_results_retained", "raw_response_retained_until"),
    )

    # ── Run FK ───────────────────────────────────────────────────────
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Scenario metadata ────────────────────────────────────────────
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    mutating: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applicable_to: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # ── Prompt & response ────────────────────────────────────────────
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected: Mapped[str] = mapped_column(String(32), nullable=False)
    actual: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ── Outcome ──────────────────────────────────────────────────────
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    skipped_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── Detector ─────────────────────────────────────────────────────
    detector_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detector_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Performance ──────────────────────────────────────────────────
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Raw response retention ───────────────────────────────────────
    raw_response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_response_retained_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────
    run: Mapped[BenchmarkRun] = relationship(back_populates="scenario_results")
