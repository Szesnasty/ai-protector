"""Request log ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin


class Request(UUIDMixin, Base):
    """Firewall request/response audit log."""

    __tablename__ = "requests"

    client_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_id: Mapped[uuid.UUID] = mapped_column(
        __import__("sqlalchemy").ForeignKey("policies.id"),
        nullable=False,
        index=True,
    )
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    prompt_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(String(16), nullable=False, default="allow")
    risk_flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_masked: Mapped[bool | None] = mapped_column(nullable=True, default=False)
    scanner_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_filter_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    node_timings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    policy: Mapped[Policy] = relationship(back_populates="requests", lazy="selectin")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Request client={self.client_id!r} decision={self.decision!r}>"
