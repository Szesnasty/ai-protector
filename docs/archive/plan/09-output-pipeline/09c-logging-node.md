# Step 09c — Logging Node (Postgres + Langfuse)

| | |
|---|---|
| **Parent** | [Step 09 — Output Pipeline](SPEC.md) |
| **Estimated time** | 2.5–3 hours |
| **Depends on** | Step 09a (output_filter), Step 09b (memory hygiene) |

---

## Goal

Replace the current fire-and-forget `asyncio.create_task(log_request(...))` pattern with a **dedicated pipeline node** that:

1. Writes the full audit record to **PostgreSQL** (enhanced `requests` table)
2. Sends a structured **Langfuse trace** with spans for each pipeline stage

The logging node runs on **all paths** (ALLOW, MODIFY, BLOCK), making it the last node before returning the response.

---

## Scope

### In scope
- New file `src/pipeline/nodes/logging_node.py` (pipeline node)
- Refactor `src/services/request_logger.py` to be called from the pipeline node
- New file `src/services/langfuse_client.py` — Langfuse SDK wrapper
- Enhanced Request model: add `scanner_results` JSONB column, `output_filter_results` JSONB column, `node_timings` JSONB column
- Alembic migration for new columns
- Langfuse trace with spans: one span per pipeline node using `node_timings`
- Unit tests for both Postgres logging and Langfuse trace creation

### Out of scope
- Langfuse prompt management
- Langfuse evaluation/scoring (future step)
- Streaming trace updates
- Dashboard queries (Step 10+)

---

## Technical Design

### 1. Langfuse Client (`src/services/langfuse_client.py`)

```python
"""Langfuse client singleton for tracing."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog
from langfuse import Langfuse

from src.config import get_settings

logger = structlog.get_logger()


@lru_cache
def get_langfuse() -> Langfuse | None:
    """Return Langfuse client or None if config is missing."""
    settings = get_settings()
    try:
        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception:
        logger.warning("langfuse_init_failed")
        return None


async def create_trace(
    *,
    trace_id: str,
    name: str = "ai-protector-request",
    input_data: dict[str, Any],
    output_data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> None:
    """Create a Langfuse trace with pipeline data.

    Non-blocking. Errors are swallowed and logged.
    """
    client = get_langfuse()
    if client is None:
        return

    try:
        trace = client.trace(
            id=trace_id,
            name=name,
            input=input_data,
            output=output_data,
            metadata=metadata,
            tags=tags or [],
            user_id=user_id,
            session_id=session_id,
        )
        return trace
    except Exception:
        logger.exception("langfuse_trace_failed")


async def add_pipeline_spans(
    trace: Any,
    node_timings: dict[str, float],
    state: dict,
) -> None:
    """Add a span for each pipeline node to the trace."""
    if trace is None:
        return

    for node_name, duration_ms in node_timings.items():
        try:
            trace.span(
                name=node_name,
                metadata={"duration_ms": duration_ms},
            )
        except Exception:
            logger.warning("langfuse_span_failed", node=node_name)
```

### 2. Logging Pipeline Node (`src/pipeline/nodes/logging_node.py`)

```python
"""LoggingNode — audit log to Postgres + Langfuse trace."""

from __future__ import annotations

from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState
from src.services.request_logger import log_request_from_state
from src.services.langfuse_client import create_trace, add_pipeline_spans


@timed_node("logging")
async def logging_node(state: PipelineState) -> PipelineState:
    """Write audit record to Postgres and send Langfuse trace.

    Errors are swallowed — logging must never block the response.
    """
    # 1. Postgres audit log
    await log_request_from_state(state)

    # 2. Langfuse trace
    trace = await create_trace(
        trace_id=state.get("request_id", ""),
        input_data={
            "messages": state.get("sanitized_messages") or state.get("messages", []),
            "model": state.get("model", ""),
            "policy": state.get("policy_name", ""),
        },
        output_data={
            "decision": state.get("decision", ""),
            "risk_score": state.get("risk_score", 0.0),
            "response": _safe_response_preview(state),
        },
        metadata={
            "intent": state.get("intent"),
            "risk_flags": state.get("risk_flags", {}),
            "scanner_results_summary": _scanner_summary(state),
            "output_filter_results": state.get("output_filter_results", {}),
            "node_timings": state.get("node_timings", {}),
        },
        tags=_build_tags(state),
        user_id=state.get("client_id"),
    )

    await add_pipeline_spans(
        trace,
        state.get("node_timings", {}),
        state,
    )

    return state  # Logging doesn't modify state


def _safe_response_preview(state: PipelineState, max_len: int = 500) -> str | None:
    """Extract first N chars of LLM response for trace."""
    resp = state.get("llm_response")
    if not resp:
        return None
    try:
        content = resp["choices"][0]["message"]["content"]
        return content[:max_len]
    except (KeyError, IndexError):
        return None


def _scanner_summary(state: PipelineState) -> dict:
    """Compact scanner results for Langfuse metadata."""
    results = state.get("scanner_results", {})
    summary = {}
    for scanner_name, data in results.items():
        if isinstance(data, dict):
            summary[scanner_name] = {
                k: v for k, v in data.items()
                if k in ("is_valid", "score", "pii_action", "entity_count", "pii_count")
            }
    return summary


def _build_tags(state: PipelineState) -> list[str]:
    """Build Langfuse tags from state."""
    tags = [f"decision:{state.get('decision', 'unknown')}"]
    if state.get("policy_name"):
        tags.append(f"policy:{state['policy_name']}")
    if state.get("intent"):
        tags.append(f"intent:{state['intent']}")
    if state.get("output_filtered"):
        tags.append("output_filtered")
    return tags
```

### 3. Refactored `request_logger.py`

Add a new function that takes `PipelineState` directly:

```python
async def log_request_from_state(state: PipelineState) -> None:
    """Write audit row from full pipeline state.

    Replaces the old log_request() for pipeline-integrated logging.
    Old function kept for backward compatibility with chat router.
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
            scanner_results=state.get("scanner_results", {}),       # NEW
            output_filter_results=state.get("output_filter_results", {}),  # NEW
            node_timings=state.get("node_timings", {}),             # NEW
            response_masked=state.get("response_masked", False),
        )

        async with async_session() as session:
            session.add(row)
            await session.commit()

        logger.debug("request_logged", client_id=row.client_id, decision=row.decision)
    except Exception:
        logger.exception("log_request_from_state_failed")
```

### 4. Request Model — New Columns

```python
# Add to Request model:
scanner_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
output_filter_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
node_timings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

### 5. Alembic Migration

```python
"""Add scanner_results, output_filter_results, node_timings to requests.

Revision ID: auto-generated
"""

def upgrade() -> None:
    op.add_column("requests", sa.Column("scanner_results", JSONB, nullable=True))
    op.add_column("requests", sa.Column("output_filter_results", JSONB, nullable=True))
    op.add_column("requests", sa.Column("node_timings", JSONB, nullable=True))

def downgrade() -> None:
    op.drop_column("requests", "node_timings")
    op.drop_column("requests", "output_filter_results")
    op.drop_column("requests", "scanner_results")
```

---

## Router Refactor

Remove `asyncio.create_task(log_request(...))` from `src/routers/chat.py`. Logging now happens in the pipeline. The router just returns the response from the pipeline state.

```python
# Before (chat.py):
asyncio.create_task(log_request(client_id=..., policy_name=..., ...))

# After (chat.py):
# Logging handled by logging_node in pipeline — no explicit call needed
```

---

## Dependencies

Add to `pyproject.toml`:

```toml
langfuse = ">=2.0,<3.0"
```

---

## Configuration

Existing settings in `src/config.py` are sufficient:

```python
langfuse_host: str = "http://localhost:3001"
langfuse_public_key: str = "pk-lf-local"
langfuse_secret_key: str = "sk-lf-local"
```

Add optional toggle:

```python
enable_langfuse: bool = True  # Set False to disable tracing
```

---

## Tests

### Unit tests

| File | # | Test | Assert |
|------|---|------|--------|
| `test_logging_node.py` | 1 | ALLOW state → Postgres row created | Row exists with correct fields |
| | 2 | BLOCK state → Postgres row created | `decision=BLOCK`, `blocked_reason` set |
| | 3 | MODIFY state → Postgres row created | `response_masked=True` |
| | 4 | Scanner results saved to DB | JSONB column populated |
| | 5 | Output filter results saved | JSONB column populated |
| | 6 | Node timings saved | JSONB column populated |
| | 7 | Logging failure → swallowed | No exception, state returned |
| | 8 | Node doesn't modify state | Return value == input state |
| `test_langfuse_client.py` | 1 | `get_langfuse()` returns client | Not None |
| | 2 | `create_trace` with valid data | No exception |
| | 3 | `create_trace` with Langfuse down → swallowed | No exception |
| | 4 | `add_pipeline_spans` creates spans | One per node |
| | 5 | `get_langfuse()` with bad config → None | Returns None |
| `test_request_logger_refactor.py` | 1 | `log_request_from_state()` writes row | Row in DB |
| | 2 | Old `log_request()` still works | Backward compat |
| | 3 | Unknown policy → warning, no crash | No row created |

---

## Files to create/modify

| Action | File |
|--------|------|
| **Create** | `src/services/langfuse_client.py` |
| **Create** | `src/pipeline/nodes/logging_node.py` |
| **Create** | `tests/pipeline/nodes/test_logging_node.py` |
| **Create** | `tests/services/test_langfuse_client.py` |
| **Modify** | `src/services/request_logger.py` — add `log_request_from_state()` |
| **Modify** | `src/models/request.py` — add 3 JSONB columns |
| **Modify** | `src/config.py` — add `enable_langfuse` |
| **Create** | Alembic migration |
| *(09d)* | `src/routers/chat.py` — remove `create_task(log_request(...))` |
| *(09d)* | `src/pipeline/graph.py` — wire `logging_node` |

---

## Definition of Done

- [x] `logging_node` writes to Postgres with full pipeline data
- [x] Langfuse trace created with spans for each pipeline stage
- [x] `log_request_from_state()` accepts full pipeline state
- [x] 3 new JSONB columns in `requests` table via migration
- [x] Langfuse client gracefully handles connection failures
- [x] Old `log_request()` still works (backward compat)
- [x] All 16 tests pass
- [x] `ruff check` clean
