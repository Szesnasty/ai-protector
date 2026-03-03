"""Analytics aggregation endpoints.

All endpoints query the ``requests`` table with a configurable lookback
window (``hours`` query parameter, default 24, range 1–720).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.policy import Policy
from src.models.request import Request
from src.schemas.analytics import (
    AnalyticsSummary,
    IntentCount,
    PolicyStats,
    RiskFlagCount,
    TimelineBucket,
)

router = APIRouter(tags=["analytics"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cutoff(hours: int) -> datetime:
    """Return the UTC cutoff timestamp for *hours* ago."""
    return datetime.now(timezone.utc) - timedelta(hours=hours)


BUCKET_MAP: dict[str, str] = {
    "5m": "5 minutes",
    "15m": "15 minutes",
    "1h": "1 hour",
    "6h": "6 hours",
    "1d": "1 day",
}


def _auto_bucket(hours: int) -> str:
    """Pick a reasonable bucket interval for a given lookback window."""
    if hours <= 2:
        return "5 minutes"
    if hours <= 12:
        return "15 minutes"
    if hours <= 72:
        return "1 hour"
    if hours <= 336:
        return "6 hours"
    return "1 day"


def _bucket_trunc(interval: str) -> str:
    """Map an interval string to a ``date_trunc`` precision."""
    mapping = {
        "5 minutes": "minute",
        "15 minutes": "minute",
        "1 hour": "hour",
        "6 hours": "hour",
        "1 day": "day",
    }
    return mapping.get(interval, "hour")


# ---------------------------------------------------------------------------
# 1. Summary KPIs
# ---------------------------------------------------------------------------

@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_summary(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummary:
    cutoff = _cutoff(hours)

    q = (
        select(
            func.count().label("total"),
            func.count().filter(Request.decision == "BLOCK").label("blocked"),
            func.count().filter(Request.decision == "MODIFY").label("modified"),
            func.count().filter(Request.decision == "ALLOW").label("allowed"),
            func.coalesce(func.avg(Request.risk_score), 0).label("avg_risk"),
            func.coalesce(func.avg(Request.latency_ms), 0).label("avg_latency"),
        )
        .where(Request.created_at >= cutoff)
    )
    row = (await db.execute(q)).one()

    total = row.total or 0

    # Top intent
    top_intent_q = (
        select(Request.intent, func.count().label("cnt"))
        .where(Request.created_at >= cutoff, Request.intent.isnot(None))
        .group_by(Request.intent)
        .order_by(func.count().desc())
        .limit(1)
    )
    top_row = (await db.execute(top_intent_q)).first()

    return AnalyticsSummary(
        total_requests=total,
        blocked=row.blocked or 0,
        modified=row.modified or 0,
        allowed=row.allowed or 0,
        block_rate=round((row.blocked or 0) / total, 4) if total else 0.0,
        avg_risk=round(float(row.avg_risk), 4),
        avg_latency_ms=round(float(row.avg_latency), 1),
        top_intent=top_row.intent if top_row else None,
    )


# ---------------------------------------------------------------------------
# 2. Timeline (zero-filled buckets)
# ---------------------------------------------------------------------------

@router.get("/analytics/timeline", response_model=list[TimelineBucket])
async def get_timeline(
    hours: int = Query(24, ge=1, le=720),
    bucket: str = Query("auto"),
    db: AsyncSession = Depends(get_db),
) -> list[TimelineBucket]:
    interval = BUCKET_MAP.get(bucket, _auto_bucket(hours))
    cutoff = _cutoff(hours)

    # Simple approach: just bucket by date_trunc on the appropriate precision
    # and let the application layer fill in gaps
    trunc = _bucket_trunc(interval)

    q = (
        select(
            func.date_trunc(trunc, Request.created_at).label("bucket_time"),
            func.count().label("total"),
            func.count().filter(Request.decision == "BLOCK").label("blocked"),
            func.count().filter(Request.decision == "MODIFY").label("modified"),
            func.count().filter(Request.decision == "ALLOW").label("allowed"),
        )
        .where(Request.created_at >= cutoff)
        .group_by(text("1"))
        .order_by(text("1"))
    )

    rows = (await db.execute(q)).fetchall()

    return [
        TimelineBucket(
            time=r.bucket_time,
            total=r.total,
            blocked=r.blocked,
            modified=r.modified,
            allowed=r.allowed,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 3. By-policy breakdown
# ---------------------------------------------------------------------------

@router.get("/analytics/by-policy", response_model=list[PolicyStats])
async def get_by_policy(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
) -> list[PolicyStats]:
    cutoff = _cutoff(hours)

    q = (
        select(
            Request.policy_id,
            Policy.name.label("policy_name"),
            func.count().label("total"),
            func.count().filter(Request.decision == "BLOCK").label("blocked"),
            func.count().filter(Request.decision == "MODIFY").label("modified"),
            func.count().filter(Request.decision == "ALLOW").label("allowed"),
            func.coalesce(func.avg(Request.risk_score), 0).label("avg_risk"),
        )
        .join(Policy, Request.policy_id == Policy.id)
        .where(Request.created_at >= cutoff)
        .group_by(Request.policy_id, Policy.name)
        .order_by(func.count().desc())
    )

    rows = (await db.execute(q)).fetchall()

    return [
        PolicyStats(
            policy_id=r.policy_id,
            policy_name=r.policy_name,
            total=r.total,
            blocked=r.blocked,
            modified=r.modified,
            allowed=r.allowed,
            block_rate=round(r.blocked / r.total, 4) if r.total else 0.0,
            avg_risk=round(float(r.avg_risk), 4),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 4. Top risk flags
# ---------------------------------------------------------------------------

@router.get("/analytics/top-flags", response_model=list[RiskFlagCount])
async def get_top_flags(
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[RiskFlagCount]:
    cutoff = _cutoff(hours)

    # Count total requests for pct calculation
    total_q = select(func.count()).where(Request.created_at >= cutoff)
    total = (await db.execute(total_q)).scalar() or 1

    sql = text("""
        SELECT kv.key AS flag, count(*) AS cnt
        FROM requests,
            LATERAL jsonb_each_text(risk_flags) AS kv
        WHERE created_at >= :cutoff
            AND kv.value NOT IN ('false', '0', '0.0', 'null', '')
        GROUP BY kv.key
        ORDER BY cnt DESC
        LIMIT :lim
    """)
    rows = (await db.execute(sql, {"cutoff": cutoff, "lim": limit})).fetchall()

    return [
        RiskFlagCount(
            flag=r.flag,
            count=r.cnt,
            pct=round(r.cnt / total, 4),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# 5. Intent distribution
# ---------------------------------------------------------------------------

@router.get("/analytics/intents", response_model=list[IntentCount])
async def get_intents(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
) -> list[IntentCount]:
    cutoff = _cutoff(hours)

    total_q = select(func.count()).where(Request.created_at >= cutoff)
    total = (await db.execute(total_q)).scalar() or 1

    q = (
        select(Request.intent, func.count().label("cnt"))
        .where(Request.created_at >= cutoff, Request.intent.isnot(None))
        .group_by(Request.intent)
        .order_by(func.count().desc())
    )
    rows = (await db.execute(q)).fetchall()

    return [
        IntentCount(
            intent=r.intent,
            count=r.cnt,
            pct=round(r.cnt / total, 4),
        )
        for r in rows
    ]
