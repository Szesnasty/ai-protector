"""add scanner_results, output_filter_results, node_timings to requests

Revision ID: b1e2f3a4c5d6
Revises: a06c6c7cb3dd
Create Date: 2026-03-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1e2f3a4c5d6"
down_revision: str | Sequence[str] | None = "a06c6c7cb3dd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add JSONB columns for scanner results, output filter results and node timings."""
    op.add_column("requests", sa.Column("scanner_results", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "requests", sa.Column("output_filter_results", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column("requests", sa.Column("node_timings", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Remove JSONB columns."""
    op.drop_column("requests", "node_timings")
    op.drop_column("requests", "output_filter_results")
    op.drop_column("requests", "scanner_results")
