"""add raw_response_body to benchmark_scenario_results

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-03-25

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add raw_response_body column to benchmark_scenario_results."""
    op.add_column(
        "benchmark_scenario_results",
        sa.Column("raw_response_body", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove raw_response_body column."""
    op.drop_column("benchmark_scenario_results", "raw_response_body")
