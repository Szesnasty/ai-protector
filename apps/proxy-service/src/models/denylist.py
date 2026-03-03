"""Denylist phrase ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class DenylistPhrase(UUIDMixin, TimestampMixin, Base):
    """Blocked phrase / pattern attached to a policy."""

    __tablename__ = "denylist_phrases"
    __table_args__ = (
        Index("ix_denylist_phrases_category", "category"),
    )

    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phrase: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    is_regex: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False, default="block")
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    description: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    # Relationships
    policy: Mapped[Policy] = relationship(back_populates="denylist_phrases", lazy="selectin")  # noqa: F821

    def __repr__(self) -> str:
        return f"<DenylistPhrase phrase={self.phrase!r} category={self.category!r} action={self.action!r}>"
