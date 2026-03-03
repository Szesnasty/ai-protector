# Step 09d — Graph Update & Integration

| | |
|---|---|
| **Parent** | [Step 09 — Output Pipeline](SPEC.md) |
| **Estimated time** | 1.5–2 hours |
| **Depends on** | Step 09a, 09b, 09c |

---

## Goal

Wire the new output pipeline nodes (`output_filter`, `logging`) into the LangGraph `StateGraph`, update conditional routing, refactor the chat router to rely on pipeline-integrated logging, and write end-to-end integration tests for the full pipeline flow.

---

## Scope

### In scope
- Update `src/pipeline/graph.py` — add `output_filter` and `logging` nodes
- Update routing: all paths end at `logging` instead of `END`
- Update `src/routers/chat.py` — remove `asyncio.create_task(log_request(...))`, rely on pipeline logging
- End-to-end tests: full pipeline from parse to logging
- Integration test with mocked LLM + Langfuse

### Out of scope
- Performance benchmarking (future)
- Streaming support for output nodes

---

## Technical Design

### Updated Graph (`graph.py`)

Current graph:
```
parse → intent → rules → scanners → decision
                                       ├─ BLOCK  → END
                                       ├─ MODIFY → transform → llm_call → END
                                       └─ ALLOW  → llm_call → END
```

New graph:
```
parse → intent → rules → scanners → decision
                                       ├─ BLOCK  → logging → END
                                       ├─ MODIFY → transform → llm_call → output_filter → logging → END
                                       └─ ALLOW  → llm_call → output_filter → logging → END
```

### Implementation

```python
"""LangGraph pipeline — builds and compiles the firewall StateGraph."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.pipeline.nodes.decision import decision_node
from src.pipeline.nodes.intent import intent_node
from src.pipeline.nodes.llm_call import llm_call_node
from src.pipeline.nodes.logging_node import logging_node
from src.pipeline.nodes.output_filter import output_filter_node
from src.pipeline.nodes.parse import parse_node
from src.pipeline.nodes.rules import rules_node
from src.pipeline.nodes.scanners import parallel_scanners_node
from src.pipeline.nodes.transform import transform_node
from src.pipeline.state import PipelineState


def route_after_decision(state: PipelineState) -> str:
    """Conditional routing after DecisionNode."""
    decision = state.get("decision")
    if decision == "BLOCK":
        return "block"
    if decision == "MODIFY":
        return "modify"
    return "allow"


def build_pipeline() -> StateGraph:
    """Build and compile the firewall pipeline.

    .. code-block:: text

        parse → intent → rules → scanners → decision
                                               ├─ BLOCK  → logging → END
                                               ├─ MODIFY → transform → llm_call → output_filter → logging → END
                                               └─ ALLOW  → llm_call → output_filter → logging → END
    """
    graph = StateGraph(PipelineState)

    # Input pipeline
    graph.add_node("parse", parse_node)
    graph.add_node("intent", intent_node)
    graph.add_node("rules", rules_node)
    graph.add_node("scanners", parallel_scanners_node)
    graph.add_node("decision", decision_node)
    graph.add_node("transform", transform_node)
    graph.add_node("llm_call", llm_call_node)

    # Output pipeline
    graph.add_node("output_filter", output_filter_node)
    graph.add_node("logging", logging_node)

    # Input edges
    graph.add_edge("parse", "intent")
    graph.add_edge("intent", "rules")
    graph.add_edge("rules", "scanners")
    graph.add_edge("scanners", "decision")

    # Decision routing
    graph.add_conditional_edges(
        "decision",
        route_after_decision,
        {
            "block": "logging",         # BLOCK → logging → END
            "modify": "transform",      # MODIFY → transform → ...
            "allow": "llm_call",        # ALLOW → llm_call → ...
        },
    )

    # MODIFY path
    graph.add_edge("transform", "llm_call")

    # After LLM call → output filter → logging
    graph.add_edge("llm_call", "output_filter")
    graph.add_edge("output_filter", "logging")

    # Logging → END (terminal node for all paths)
    graph.add_edge("logging", END)

    graph.set_entry_point("parse")
    return graph.compile()


# Compile once at module level
pipeline = build_pipeline()
```

### Chat Router Refactor (`chat.py`)

```python
# REMOVE:
import asyncio
from src.services.request_logger import log_request

# REMOVE from endpoint:
asyncio.create_task(
    log_request(
        client_id=...,
        policy_name=...,
        ...
    )
)

# KEEP: Pipeline handles logging internally via logging_node
# The router just extracts the response from pipeline state
```

### Runner Update (`runner.py`)

The `run_pipeline()` and `run_pre_llm_pipeline()` functions may need adjustment:

- `run_pipeline()` already returns final state — logging happens inside the pipeline now
- `run_pre_llm_pipeline()` (if still used) should NOT include logging — it's for pre-LLM checks only

```python
async def run_pipeline(
    *,
    policy_name: str,
    messages: list[dict],
    model: str | None = None,
    client_id: str | None = None,
    stream: bool = False,
) -> PipelineState:
    """Run the full firewall pipeline including output filtering and logging."""
    # ... existing config loading ...
    
    result = await pipeline.ainvoke(initial_state)
    # No need for external log_request() — logging_node handles it
    return result
```

---

## State Additions Summary (all from 09a-09c)

```python
class PipelineState(TypedDict, total=False):
    # ... existing fields ...
    
    # Output filtering (09a)
    output_filtered: bool
    output_filter_results: dict
    
    # Memory hygiene (09b)
    sanitized_messages: list[dict] | None
    
    # (No new fields for logging — it reads existing state)
```

---

## Tests

### Integration tests (`tests/pipeline/test_full_pipeline.py`)

| # | Test | Assert |
|---|------|--------|
| 1 | Clean request → ALLOW → output_filter → logging | Response returned, DB row created |
| 2 | Injection attempt → BLOCK → logging (no output_filter) | Decision=BLOCK, logged, no LLM call |
| 3 | PII in input → MODIFY → transform → llm_call → output_filter → logging | PII masked, response filtered, DB row |
| 4 | LLM response with PII → output_filter redacts | Response content cleaned |
| 5 | LLM response with secret → output_filter redacts | Secret replaced |
| 6 | Fast policy → no output_filter | output_filter is no-op |
| 7 | Strict policy → full pipeline | All nodes run |
| 8 | DB row has scanner_results JSONB | Column populated |
| 9 | DB row has node_timings JSONB | All node names present |
| 10 | Pipeline error in logging → response still returned | Graceful degradation |

### Routing tests (`tests/pipeline/test_graph_routing.py`)

| # | Test | Assert |
|---|------|--------|
| 1 | BLOCK → logging → END | Correct node sequence |
| 2 | MODIFY → transform → llm_call → output_filter → logging → END | Correct sequence |
| 3 | ALLOW → llm_call → output_filter → logging → END | Correct sequence |

### Router tests (`tests/routers/test_chat_refactor.py`)

| # | Test | Assert |
|---|------|--------|
| 1 | POST /v1/chat/completions → no `create_task(log_request)` | Logging via pipeline |
| 2 | Blocked request → 403 + logged | DB row with decision=BLOCK |
| 3 | Allowed request → 200 + logged | DB row with decision=ALLOW |

---

## Files to create/modify

| Action | File |
|--------|------|
| **Modify** | `src/pipeline/graph.py` — add output_filter + logging, update routing |
| **Modify** | `src/pipeline/runner.py` — remove external log_request calls |
| **Modify** | `src/routers/chat.py` — remove asyncio.create_task(log_request) |
| **Modify** | `src/pipeline/state.py` — add new fields (if not already done in 09a/09b) |
| **Create** | `tests/pipeline/test_full_pipeline.py` |
| **Create** | `tests/pipeline/test_graph_routing.py` |
| **Modify** | `tests/routers/test_chat.py` — update for new behavior |

---

## Migration checklist

Before running tests:
1. `alembic upgrade head` (for new columns from 09c)
2. `python -m src.db.seed` (for updated policy nodes from 09a)
3. Langfuse running on `localhost:3001` (or `enable_langfuse=False` for CI)

---

## Definition of Done

- [ ] Graph has `output_filter` and `logging` nodes
- [ ] All 3 paths (ALLOW/MODIFY/BLOCK) end at `logging → END`
- [ ] Chat router no longer calls `asyncio.create_task(log_request(...))`
- [ ] Full pipeline E2E: request → all nodes → DB row + Langfuse trace
- [ ] All 16 integration + routing + router tests pass
- [ ] Existing 175 tests still pass (backward compatibility)
- [ ] `ruff check` clean
