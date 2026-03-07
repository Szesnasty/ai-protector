"""Analytics aggregation endpoints.

All endpoints query the ``requests`` table with a configurable lookback
window (``hours`` query parameter, default 24, range 1–720).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, literal_column, select, text
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


def _cutoff(hours: float) -> datetime:
    """Return the UTC cutoff timestamp for *hours* ago."""
    return datetime.now(UTC) - timedelta(hours=hours)


BUCKET_MAP: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "1d": 86400,
}


def _auto_bucket_seconds(hours: float) -> int:
    """Pick a reasonable bucket size in seconds for a given lookback window."""
    if hours <= 0.25:  # ≤ 15 min  → 1-minute buckets
        return 60
    if hours <= 1:  # ≤ 1 h     → 2-minute buckets
        return 120
    if hours <= 6:  # ≤ 6 h     → 5-minute buckets
        return 300
    if hours <= 24:  # ≤ 24 h    → 15-minute buckets
        return 900
    if hours <= 72:  # ≤ 3 d     → 1-hour buckets
        return 3600
    if hours <= 336:  # ≤ 14 d    → 6-hour buckets
        return 21600
    return 86400  # else      → 1-day buckets


def _epoch_bucket(seconds: int):
    """Return a SQLAlchemy expression that buckets created_at into *seconds*-wide bins.

    Uses: to_timestamp(floor(extract(epoch from created_at) / N) * N)
    This gives correct 5-minute, 15-minute, etc. boundaries aligned to epoch.
    """
    epoch = func.extract("epoch", Request.created_at)
    floored = func.floor(epoch / seconds) * seconds
    return func.to_timestamp(floored).label("bucket_time")


# ---------------------------------------------------------------------------
# 1. Summary KPIs
# ---------------------------------------------------------------------------


@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_summary(
    hours: float = Query(24, ge=0.05, le=720),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummary:
    cutoff = _cutoff(hours)

    q = select(
        func.count().label("total"),
        func.count().filter(Request.decision == "BLOCK").label("blocked"),
        func.count().filter(Request.decision == "MODIFY").label("modified"),
        func.count().filter(Request.decision == "ALLOW").label("allowed"),
        func.coalesce(func.avg(Request.risk_score), 0).label("avg_risk"),
        func.coalesce(func.avg(Request.latency_ms), 0).label("avg_latency"),
    ).where(Request.created_at >= cutoff)
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
    hours: float = Query(24, ge=0.05, le=720),
    bucket: str = Query("auto"),
    db: AsyncSession = Depends(get_db),
) -> list[TimelineBucket]:
    bucket_secs = BUCKET_MAP.get(bucket, _auto_bucket_seconds(hours))
    cutoff = _cutoff(hours)
    bucket_expr = _epoch_bucket(bucket_secs)

    q = (
        select(
            bucket_expr,
            func.count().label("total"),
            func.count().filter(Request.decision == "BLOCK").label("blocked"),
            func.count().filter(Request.decision == "MODIFY").label("modified"),
            func.count().filter(Request.decision == "ALLOW").label("allowed"),
        )
        .where(Request.created_at >= cutoff)
        .group_by(literal_column("bucket_time"))
        .order_by(literal_column("bucket_time"))
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
    hours: float = Query(24, ge=0.05, le=720),
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
    hours: float = Query(24, ge=0.05, le=720),
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
    hours: float = Query(24, ge=0.05, le=720),
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
