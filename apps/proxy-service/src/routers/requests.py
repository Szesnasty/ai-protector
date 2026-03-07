"""Paginated request-log router."""

from __future__ import annotations

import math
import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.request import Request
from src.schemas.request import PaginatedResponse, RequestDetail, RequestRead

logger = structlog.get_logger()

router = APIRouter(tags=["requests"])

ALLOWED_SORT_COLUMNS: dict[str, object] = {
    "created_at": Request.created_at,
    "decision": Request.decision,
    "risk_score": Request.risk_score,
    "latency_ms": Request.latency_ms,
    "client_id": Request.client_id,
}


@router.get("/requests", response_model=PaginatedResponse[RequestRead])
async def list_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort: str = Query("created_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    decision: str | None = Query(None),
    intent: str | None = Query(None),
    policy_id: uuid.UUID | None = Query(None),
    client_id: str | None = Query(None),
    risk_min: float | None = Query(None, ge=0, le=1),
    risk_max: float | None = Query(None, ge=0, le=1),
    search: str | None = Query(None),
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """List request log entries with server-side pagination, sorting, and filters."""
    stmt = select(Request)

    # -- filters --
    if decision:
        stmt = stmt.where(Request.decision == decision.upper())
    if intent:
        stmt = stmt.where(Request.intent == intent)
    if policy_id:
        stmt = stmt.where(Request.policy_id == policy_id)
    if client_id:
        stmt = stmt.where(Request.client_id == client_id)
    if risk_min is not None:
        stmt = stmt.where(Request.risk_score >= risk_min)
    if risk_max is not None:
        stmt = stmt.where(Request.risk_score <= risk_max)
    if search:
        stmt = stmt.where(Request.prompt_preview.ilike(f"%{search}%"))
    if date_from:
        stmt = stmt.where(Request.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Request.created_at <= date_to)

    # -- count total --
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # -- sort --
    sort_col = ALLOWED_SORT_COLUMNS.get(sort, Request.created_at)
    stmt = stmt.order_by(sort_col.desc() if order == "desc" else sort_col.asc())  # type: ignore[union-attr]

    # -- paginate --
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Attach policy_name via the eager-loaded relationship
    items = []
    for row in rows:
        data = RequestRead.model_validate(row)
        data.policy_name = row.policy.name if row.policy else ""
        items.append(data)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, math.ceil(total / page_size)),
    }


@router.get("/requests/{request_id}", response_model=RequestDetail)
async def get_request_detail(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> RequestDetail:
    """Get full details for a single request."""
    row = await db.get(Request, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    detail = RequestDetail.model_validate(row)
    detail.policy_name = row.policy.name if row.policy else ""
    return detail
