"""aw_006_traces_incidents_gates_promotions

Revision ID: a1b2c3d4e5f6
Revises: 10106fb845f3
Create Date: 2026-03-17 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "10106fb845f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Pure SQL migration — bypasses asyncpg/SQLAlchemy enum handling issues.


def upgrade() -> None:
    """Create traces, incidents, gate_decisions, and promotion_events tables."""
    conn = op.get_bind()

    # ── Enums (DO $$ swallows duplicates) ────────────────────────────
    enums = [
        ("trace_gate", "'pre_tool','post_tool','pre_llm','post_llm'"),
        ("trace_decision", "'ALLOW','DENY','REDACT','WARN'"),
        ("incident_severity", "'low','medium','high','critical'"),
        ("incident_category", "'rbac_violation','injection_attempt','pii_leak','budget_exceeded'"),
        ("incident_status", "'open','acknowledged','resolved','false_positive'"),
        ("gate_decision_type", "'rbac','injection','pii','budget'"),
        ("gate_action", "'allow','deny','block','redact','warn'"),
    ]
    for name, vals in enums:
        conn.execute(
            sa.text(
                f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({vals}); EXCEPTION WHEN duplicate_object THEN NULL; END $$"
            )
        )

    # ── Tables (IF NOT EXISTS for idempotency) ───────────────────────
    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS agent_incidents (
            id          UUID PRIMARY KEY,
            agent_id    UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            severity    incident_severity NOT NULL,
            category    incident_category NOT NULL,
            title       VARCHAR(256) NOT NULL,
            status      incident_status NOT NULL DEFAULT 'open',
            first_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
            trace_count INTEGER NOT NULL DEFAULT 1,
            details     JSONB
        )
    """)
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_agent_incidents_agent_id ON agent_incidents(agent_id)"))

    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS agent_traces (
            id           UUID PRIMARY KEY,
            agent_id     UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            session_id   VARCHAR(128) NOT NULL DEFAULT 'default',
            timestamp    TIMESTAMPTZ NOT NULL DEFAULT now(),
            gate         trace_gate NOT NULL,
            tool_name    VARCHAR(128),
            role         VARCHAR(128),
            decision     trace_decision NOT NULL,
            reason       TEXT NOT NULL DEFAULT '',
            category     VARCHAR(64) NOT NULL DEFAULT 'policy',
            rollout_mode rollout_mode NOT NULL,
            enforced     BOOLEAN NOT NULL DEFAULT true,
            latency_ms   INTEGER NOT NULL DEFAULT 0,
            details      JSONB,
            incident_id  UUID REFERENCES agent_incidents(id) ON DELETE SET NULL
        )
    """)
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_agent_traces_agent_timestamp ON agent_traces(agent_id, timestamp)")
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_agent_traces_agent_session ON agent_traces(agent_id, session_id)")
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_agent_traces_incident_id ON agent_traces(incident_id)"))

    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS gate_decisions (
            id               UUID PRIMARY KEY,
            agent_id         UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            gate_type        gate_decision_type NOT NULL,
            decision         gate_action NOT NULL,
            effective_action gate_action NOT NULL,
            rollout_mode     rollout_mode NOT NULL,
            enforced         BOOLEAN NOT NULL DEFAULT true,
            warning          TEXT,
            context          JSONB,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_gate_decisions_agent_id ON gate_decisions(agent_id)"))

    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS promotion_events (
            id         UUID PRIMARY KEY,
            agent_id   UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            from_mode  rollout_mode NOT NULL,
            to_mode    rollout_mode NOT NULL,
            "user"     VARCHAR(128) NOT NULL DEFAULT 'system',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_promotion_events_agent_id ON promotion_events(agent_id)"))


def downgrade() -> None:
    """Drop tables and enums."""
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS promotion_events CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS gate_decisions CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS agent_traces CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS agent_incidents CASCADE"))
    conn.execute(sa.text("DROP TYPE IF EXISTS gate_action"))
    conn.execute(sa.text("DROP TYPE IF EXISTS gate_decision_type"))
    conn.execute(sa.text("DROP TYPE IF EXISTS incident_status"))
    conn.execute(sa.text("DROP TYPE IF EXISTS incident_category"))
    conn.execute(sa.text("DROP TYPE IF EXISTS incident_severity"))
    conn.execute(sa.text("DROP TYPE IF EXISTS trace_decision"))
    conn.execute(sa.text("DROP TYPE IF EXISTS trace_gate"))
