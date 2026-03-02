"""Policy ORM model."""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class Policy(UUIDMixin, TimestampMixin, Base):
    """Firewall policy configuration."""

    __tablename__ = "policies"

    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)

    # Relationships
    requests: Mapped[list[Request]] = relationship(back_populates="policy", lazy="selectin")  # noqa: F821
    denylist_phrases: Mapped[list[DenylistPhrase]] = relationship(  # noqa: F821
        back_populates="policy",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Policy name={self.name!r} active={self.is_active}>"
