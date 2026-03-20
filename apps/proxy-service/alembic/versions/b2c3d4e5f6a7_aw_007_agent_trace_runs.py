"""aw_007_agent_trace_runs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-20 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create agent_trace_runs table for structured traces."""
    conn = op.get_bind()
    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS agent_trace_runs (
            id                UUID PRIMARY KEY,
            agent_id          UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            trace_id          VARCHAR(64) NOT NULL UNIQUE,
            session_id        VARCHAR(128) NOT NULL DEFAULT 'default',
            timestamp         TIMESTAMPTZ NOT NULL DEFAULT now(),
            user_role         VARCHAR(128) NOT NULL DEFAULT 'user',
            model             VARCHAR(128) NOT NULL DEFAULT '',
            intent            VARCHAR(128),
            total_duration_ms INTEGER NOT NULL DEFAULT 0,
            counters          JSONB NOT NULL DEFAULT '{}',
            iterations        JSONB NOT NULL DEFAULT '[]',
            errors            JSONB NOT NULL DEFAULT '[]',
            limits_hit        VARCHAR(64),
            details           JSONB
        )
        """)
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_trace_runs_agent_timestamp ON agent_trace_runs (agent_id, timestamp)")
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_trace_runs_agent_session ON agent_trace_runs (agent_id, session_id)")
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_trace_runs_agent_id ON agent_trace_runs (agent_id)"))


def downgrade() -> None:
    """Drop agent_trace_runs table."""
    op.drop_table("agent_trace_runs")
