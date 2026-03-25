"""add protection_detected and proxy_blocked_count to benchmark_runs

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-03-26

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add protection detection columns to benchmark_runs."""
    op.add_column(
        "benchmark_runs",
        sa.Column("protection_detected", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "benchmark_runs",
        sa.Column("proxy_blocked_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Remove protection detection columns."""
    op.drop_column("benchmark_runs", "proxy_blocked_count")
    op.drop_column("benchmark_runs", "protection_detected")
