"""add rule action severity description columns

Revision ID: c3d4e5f6a7b8
Revises: b1e2f3a4c5d6
Create Date: 2025-01-15 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b1e2f3a4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add action, severity, description columns to denylist_phrases."""
    op.add_column(
        "denylist_phrases",
        sa.Column("action", sa.String(16), nullable=False, server_default="block"),
    )
    op.add_column(
        "denylist_phrases",
        sa.Column("severity", sa.String(16), nullable=False, server_default="medium"),
    )
    op.add_column(
        "denylist_phrases",
        sa.Column("description", sa.String(256), nullable=False, server_default=""),
    )
    op.create_index("ix_denylist_phrases_category", "denylist_phrases", ["category"])


def downgrade() -> None:
    """Remove action, severity, description columns from denylist_phrases."""
    op.drop_index("ix_denylist_phrases_category", table_name="denylist_phrases")
    op.drop_column("denylist_phrases", "description")
    op.drop_column("denylist_phrases", "severity")
    op.drop_column("denylist_phrases", "action")
