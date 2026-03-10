"""Trace recorder service (spec 32c).

Records per-gate evaluation traces and groups them into incidents.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.wizard.models import (
    AgentIncident,
    AgentTrace,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    RolloutMode,
    TraceDecision,
    TraceGate,
)

logger = structlog.get_logger()

# ── Severity mapping ────────────────────────────────────────────────

_CATEGORY_TO_INCIDENT: dict[str, IncidentCategory] = {
    "rbac": IncidentCategory.RBAC_VIOLATION,
    "injection": IncidentCategory.INJECTION_ATTEMPT,
    "pii": IncidentCategory.PII_LEAK,
    "budget": IncidentCategory.BUDGET_EXCEEDED,
}

INCIDENT_WINDOW = timedelta(hours=1)


def compute_severity(
    category: str,
    decision: TraceDecision,
    rollout_mode: RolloutMode,
) -> IncidentSeverity:
    """Determine incident severity (deterministic, no LLM)."""
    # Observe/warn → always LOW (informational)
    if rollout_mode in (RolloutMode.OBSERVE, RolloutMode.WARN):
        return IncidentSeverity.LOW

    # Enforce mode
    if category == "injection":
        return IncidentSeverity.CRITICAL
    if category in ("rbac", "pii"):
        return IncidentSeverity.HIGH
    if category == "budget":
        return IncidentSeverity.MEDIUM
    return IncidentSeverity.MEDIUM


def _build_incident_title(
    category: str,
    role: str | None,
    tool_name: str | None,
    reason: str,
) -> str:
    """Generate a human-readable incident title."""
    cat_label = category.replace("_", " ").title()
    parts = [cat_label]
    if role:
        parts.append(f"role={role}")
    if tool_name:
        parts.append(f"tool={tool_name}")
    if reason:
        parts.append(reason[:80])
    return ": ".join(parts[:2]) if len(parts) > 1 else parts[0]


class TraceRecorder:
    """Records gate decisions as traces and groups them into incidents."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record(
        self,
        *,
        agent_id: uuid.UUID,
        session_id: str = "default",
        gate: TraceGate,
        tool_name: str | None = None,
        role: str | None = None,
        decision: TraceDecision,
        reason: str = "",
        category: str = "policy",
        rollout_mode: RolloutMode = RolloutMode.OBSERVE,
        enforced: bool = True,
        latency_ms: int = 0,
        details: dict | None = None,
    ) -> AgentTrace:
        """Record a single gate evaluation trace.

        If decision is DENY/REDACT/WARN, also create or update an incident.
        """
        now = datetime.now(UTC)

        trace = AgentTrace(
            agent_id=agent_id,
            session_id=session_id,
            timestamp=now,
            gate=gate,
            tool_name=tool_name,
            role=role,
            decision=decision,
            reason=reason,
            category=category,
            rollout_mode=rollout_mode,
            enforced=enforced,
            latency_ms=latency_ms,
            details=details,
        )

        # Link to incident if not ALLOW
        if decision != TraceDecision.ALLOW:
            incident = await self._find_or_create_incident(
                agent_id=agent_id,
                category=category,
                decision=decision,
                rollout_mode=rollout_mode,
                role=role,
                tool_name=tool_name,
                reason=reason,
                now=now,
            )
            trace.incident_id = incident.id

        self._db.add(trace)
        await self._db.commit()
        await self._db.refresh(trace)

        logger.debug(
            "trace_recorded",
            agent_id=str(agent_id),
            gate=gate.value,
            decision=decision.value,
            incident_id=str(trace.incident_id) if trace.incident_id else None,
        )

        return trace

    async def _find_or_create_incident(
        self,
        *,
        agent_id: uuid.UUID,
        category: str,
        decision: TraceDecision,
        rollout_mode: RolloutMode,
        role: str | None,
        tool_name: str | None,
        reason: str,
        now: datetime,
    ) -> AgentIncident:
        """Find existing incident (same agent+category within window) or create new."""
        incident_cat = _CATEGORY_TO_INCIDENT.get(category, IncidentCategory.RBAC_VIOLATION)
        window_start = now - INCIDENT_WINDOW

        result = await self._db.execute(
            select(AgentIncident)
            .where(
                and_(
                    AgentIncident.agent_id == agent_id,
                    AgentIncident.category == incident_cat,
                    AgentIncident.last_seen >= window_start,
                    AgentIncident.status.in_(
                        [
                            IncidentStatus.OPEN,
                            IncidentStatus.ACKNOWLEDGED,
                        ]
                    ),
                )
            )
            .order_by(AgentIncident.last_seen.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            # Update existing incident
            existing.last_seen = now
            existing.trace_count += 1
            self._db.add(existing)
            await self._db.flush()
            return existing

        # Create new incident
        severity = compute_severity(category, decision, rollout_mode)
        title = _build_incident_title(category, role, tool_name, reason)

        incident = AgentIncident(
            agent_id=agent_id,
            severity=severity,
            category=incident_cat,
            title=title,
            status=IncidentStatus.OPEN,
            first_seen=now,
            last_seen=now,
            trace_count=1,
            details={"initial_decision": decision.value},
        )
        self._db.add(incident)
        await self._db.flush()
        await self._db.refresh(incident)
        return incident
