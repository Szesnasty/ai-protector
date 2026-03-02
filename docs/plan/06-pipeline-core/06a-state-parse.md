# 06a — Pipeline State & ParseNode

| | |
|---|---|
| **Parent** | [Step 06 — Pipeline Core](SPEC.md) |
| **Next sub-step** | [06b — Intent & Rules Nodes](06b-intent-rules.md) |
| **Estimated time** | 1–1.5 hours |

---

## Goal

Define the `PipelineState` TypedDict that flows through all pipeline nodes, and implement the first node — `ParseNode` — that extracts and normalizes the incoming request.

---

## Tasks

### 1. Pipeline state (`src/pipeline/state.py`)

- [ ] Create `src/pipeline/` package with `__init__.py`
- [ ] Define the shared state:
  ```python
  from typing import TypedDict, Literal, Any

  class PipelineState(TypedDict, total=False):
      # ── Input (set by ParseNode) ──
      request_id: str                    # UUID, same as x-correlation-id
      client_id: str | None
      policy_name: str                   # "fast" | "balanced" | "strict" | "paranoid"
      policy_config: dict                # Full policy config JSONB from DB
      model: str
      messages: list[dict]               # Full conversation
      user_message: str                  # Extracted last user message
      prompt_hash: str                   # SHA-256 of user_message
      temperature: float
      max_tokens: int | None
      stream: bool

      # ── Analysis (accumulated by nodes) ──
      intent: str | None                 # "qa" | "code_gen" | "tool_call" | "chitchat" | ...
      intent_confidence: float           # 0.0–1.0
      risk_flags: dict[str, Any]         # {"injection": 0.8, "pii": ["EMAIL"], ...}
      risk_score: float                  # Aggregated 0.0–1.0
      rules_matched: list[str]           # ["denylist:bomb", "length_exceeded"]
      scanner_results: dict[str, Any]    # Results from LLM Guard, Presidio (Step 07)

      # ── Decision ──
      decision: Literal["ALLOW", "MODIFY", "BLOCK"] | None
      blocked_reason: str | None
      modified_messages: list[dict] | None

      # ── Output (set after LLM call) ──
      llm_response: dict | None
      response_masked: bool
      tokens_in: int | None
      tokens_out: int | None
      latency_ms: int | None

      # ── Metadata ──
      node_timings: dict[str, float]     # {"parse": 1.2, "intent": 45.3} (ms)
      errors: list[str]                  # Non-fatal errors from nodes
  ```
- [ ] This state is the **single source of truth** — every node reads from and writes to it

### 2. Node timing decorator (`src/pipeline/nodes/__init__.py`)

- [ ] Create `src/pipeline/nodes/` package
- [ ] Create a reusable timing helper:
  ```python
  import time
  from functools import wraps

  def timed_node(name: str):
      """Decorator that measures node execution time in ms."""
      def decorator(func):
          @wraps(func)
          async def wrapper(state):
              start = time.perf_counter()
              result = await func(state)
              elapsed = (time.perf_counter() - start) * 1000
              timings = {**result.get("node_timings", {}), name: round(elapsed, 2)}
              return {**result, "node_timings": timings}
          return wrapper
      return decorator
  ```

### 3. ParseNode (`src/pipeline/nodes/parse.py`)

- [ ] Implementation:
  ```python
  @timed_node("parse")
  async def parse_node(state: PipelineState) -> PipelineState:
      """
      Extract and normalize incoming request into pipeline state fields.
      Always runs first. Initializes all accumulator fields.
      """
      messages = state["messages"]
      
      # Extract last user message
      user_message = ""
      for msg in reversed(messages):
          if msg["role"] == "user":
              user_message = msg["content"]
              break

      prompt_hash = hashlib.sha256(user_message.encode()).hexdigest()

      return {
          **state,
          "user_message": user_message,
          "prompt_hash": prompt_hash,
          # Initialize accumulators
          "risk_flags": {},
          "risk_score": 0.0,
          "rules_matched": [],
          "scanner_results": {},
          "decision": None,
          "blocked_reason": None,
          "modified_messages": None,
          "errors": [],
          "node_timings": {},
          "response_masked": False,
      }
  ```
- [ ] Handle edge case: no user message found → set `user_message = ""` and add to `errors`

---

## Definition of Done

- [ ] `src/pipeline/state.py` — `PipelineState` TypedDict with all fields
- [ ] `src/pipeline/nodes/__init__.py` — `timed_node` decorator
- [ ] `src/pipeline/nodes/parse.py` — `parse_node` function
- [ ] ParseNode extracts `user_message` from last user message in conversation
- [ ] ParseNode computes `prompt_hash` (SHA-256 hex)
- [ ] ParseNode initializes all accumulator fields (risk_flags, errors, etc.)
- [ ] Edge case: empty messages → `user_message = ""`, error logged
- [ ] `ruff check src/` → 0 errors

---

| **Parent** | **Next** |
|---|---|
| [Step 06 — SPEC](SPEC.md) | [06b — Intent & Rules Nodes](06b-intent-rules.md) |
