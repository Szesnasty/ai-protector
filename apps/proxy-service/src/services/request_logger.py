"""Fire-and-forget request logger — writes audit rows to the requests table."""

from __future__ import annotations

import hashlib
import uuid

import structlog
from sqlalchemy import select

from src.db.session import async_session
from src.models.policy import Policy
from src.models.request import Request

logger = structlog.get_logger()

# In-memory cache: policy_name → policy_id
_policy_cache: dict[str, uuid.UUID] = {}


async def _resolve_policy_id(policy_name: str) -> uuid.UUID | None:
    """Return the UUID for a policy name, using an in-memory cache.

    Falls back to 'balanced' if the requested policy is not found,
    so that audit rows are never silently dropped.
    """
    if policy_name in _policy_cache:
        return _policy_cache[policy_name]

    async with async_session() as session:
        result = await session.execute(
            select(Policy.id).where(Policy.name == policy_name)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            _policy_cache[policy_name] = row
            return row

    # Fallback: try 'balanced' default so we never silently lose logs
    if policy_name != "balanced":
        logger.warning("policy_not_found_falling_back", requested=policy_name, fallback="balanced")
        return await _resolve_policy_id("balanced")

    return None


def _prompt_hash(messages: list[dict]) -> str | None:
    """SHA-256 hex of the last user message content."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return hashlib.sha256(msg["content"].encode()).hexdigest()
    return None


def _prompt_preview(messages: list[dict], max_len: int = 200) -> str | None:
    """First *max_len* chars of the last user message."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg["content"][:max_len]
    return None


async def log_request(
    *,
    client_id: str | None,
    policy_name: str,
    model: str,
    messages: list[dict],
    decision: str = "ALLOW",
    blocked_reason: str | None = None,
    intent: str | None = None,
    risk_flags: dict | None = None,
    risk_score: float = 0.0,
    latency_ms: int = 0,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    scanner_results: dict | None = None,
    node_timings: dict | None = None,
) -> None:
    """Write an audit row to the requests table.

    This is designed to be called via ``asyncio.create_task`` so it never
    blocks the HTTP response.  Any exception is swallowed and logged.
    """
    try:
        policy_id = await _resolve_policy_id(policy_name)
        if policy_id is None:
            logger.warning("log_request_unknown_policy", policy=policy_name)
            return

        row = Request(
            client_id=client_id or "anonymous",
            policy_id=policy_id,
            model_used=model,
            prompt_hash=_prompt_hash(messages),
            prompt_preview=_prompt_preview(messages),
            decision=decision,
            blocked_reason=blocked_reason,
            intent=intent,
            risk_flags=risk_flags or {},
            risk_score=risk_score,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            scanner_results=scanner_results or {},
            node_timings=node_timings or {},
        )

        async with async_session() as session:
            session.add(row)
            await session.commit()

        logger.debug("request_logged", client_id=row.client_id, decision=decision)
    except Exception:
        logger.exception("log_request_failed")


async def log_request_from_state(state: dict) -> None:
    """Write audit row from full pipeline state.

    Replaces the old ``log_request()`` for pipeline-integrated logging.
    The old function is kept for backward compatibility with the chat router.
    """
    try:
        policy_id = await _resolve_policy_id(state.get("policy_name", "balanced"))
        if policy_id is None:
            logger.warning("log_request_unknown_policy", policy=state.get("policy_name"))
            return

        row = Request(
            client_id=state.get("client_id") or "anonymous",
            policy_id=policy_id,
            model_used=state.get("model"),
            prompt_hash=state.get("prompt_hash"),
            prompt_preview=_prompt_preview(state.get("messages", [])),
            decision=state.get("decision", "ALLOW"),
            blocked_reason=state.get("blocked_reason"),
            intent=state.get("intent"),
            risk_flags=state.get("risk_flags", {}),
            risk_score=state.get("risk_score", 0.0),
            latency_ms=state.get("latency_ms", 0),
            tokens_in=state.get("tokens_in"),
            tokens_out=state.get("tokens_out"),
            response_masked=state.get("response_masked", False),
            scanner_results=state.get("scanner_results", {}),
            output_filter_results=state.get("output_filter_results", {}),
            node_timings=state.get("node_timings", {}),
        )

        async with async_session() as session:
            session.add(row)
            await session.commit()

        logger.debug(
            "request_logged_from_state",
            client_id=row.client_id,
            decision=row.decision,
        )
    except Exception:
        logger.exception("log_request_from_state_failed")
