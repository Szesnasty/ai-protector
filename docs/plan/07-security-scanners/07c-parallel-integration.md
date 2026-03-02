# 07c — Parallel Execution & Integration

| | |
|---|---|
| **Parent** | [Step 07 — Security Scanners](SPEC.md) |
| **Prev sub-step** | [07b — Presidio PII Node](07b-presidio.md) |
| **Estimated time** | 2–2.5 hours |

---

## Goal

Run LLM Guard and Presidio scanners **in parallel**, update the LangGraph pipeline and DecisionNode to incorporate scanner results, update TransformNode for PII masking, and verify everything end-to-end.

---

## Tasks

### 1. Parallel scanner wrapper (`src/pipeline/nodes/scanners.py`)

- [ ] Dispatch enabled scanners concurrently:
  ```python
  @timed_node("scanners")
  async def parallel_scanners_node(state: PipelineState) -> PipelineState:
      policy_nodes = state["policy_config"].get("nodes", [])

      tasks = []
      if "llm_guard" in policy_nodes:
          tasks.append(("llm_guard", llm_guard_node(state)))
      if "presidio" in policy_nodes:
          tasks.append(("presidio", presidio_node(state)))

      if not tasks:
          return state  # fast policy — skip entirely

      results = await asyncio.gather(
          *[task for _, task in tasks],
          return_exceptions=True,
      )

      # Merge scanner results into single state
      merged_flags = {**state["risk_flags"]}
      merged_scanners = {**state.get("scanner_results", {})}
      merged_errors = list(state.get("errors", []))

      for (name, _), result in zip(tasks, results):
          if isinstance(result, Exception):
              merged_errors.append(f"{name}: {result}")
              continue
          merged_flags.update(result.get("risk_flags", {}))
          merged_scanners.update(result.get("scanner_results", {}))
          merged_errors.extend(result.get("errors", []))

      return {
          **state,
          "risk_flags": merged_flags,
          "scanner_results": merged_scanners,
          "errors": merged_errors,
      }
  ```
- [ ] Scanner selection by policy:
  | Policy | Scanners |
  |--------|----------|
  | `fast` | none |
  | `balanced` | LLM Guard |
  | `strict` | LLM Guard + Presidio |
  | `paranoid` | LLM Guard + Presidio |

### 2. Update LangGraph (`src/pipeline/graph.py`)

- [ ] Insert scanners between `rules` and `decision`:
  ```python
  # Before (Step 06):
  #   parse → intent → rules → decision → ...
  
  # After (Step 07):
  #   parse → intent → rules → scanners → decision → ...

  graph.add_node("scanners", parallel_scanners_node)
  graph.add_edge("rules", "scanners")
  graph.add_edge("scanners", "decision")
  # Remove old: graph.add_edge("rules", "decision")
  ```

### 3. Update DecisionNode (`src/pipeline/nodes/decision.py`)

- [ ] Extend `calculate_risk_score()` with scanner weights:
  ```python
  # LLM Guard signals
  if "promptinjection" in flags:
      score += float(flags["promptinjection"]) * 0.8

  if "toxicity" in flags:
      score += float(flags["toxicity"]) * 0.5

  if "secrets" in flags:
      score += 0.6

  if "invisibletext" in flags:
      score += 0.4

  # Presidio PII
  pii_count = flags.get("pii_count", 0)
  if pii_count > 0:
      score += min(pii_count * 0.1, 0.5)
  ```

- [ ] Add PII action logic to `decision_node()`:
  ```python
  presidio = state.get("scanner_results", {}).get("presidio", {})
  pii_action = presidio.get("pii_action", "flag")

  # PII + block policy → BLOCK
  if pii_action == "block" and state["risk_flags"].get("pii"):
      return {**state, "decision": "BLOCK",
              "blocked_reason": "PII detected (block policy)"}

  # PII + mask policy → force MODIFY
  if pii_action == "mask" and state["risk_flags"].get("pii"):
      if risk_score <= max_risk:  # Not already blocked by threshold
          return {**state, "decision": "MODIFY", "risk_score": risk_score}
  ```

### 4. Update TransformNode (`src/pipeline/nodes/transform.py`)

- [ ] Apply PII masking when Presidio found entities and `pii_action=mask`:
  ```python
  async def transform_node(state: PipelineState) -> PipelineState:
      if state["decision"] != "MODIFY":
          return state

      messages = state.get("modified_messages") or [msg.copy() for msg in state["messages"]]

      # PII masking
      presidio = state.get("scanner_results", {}).get("presidio", {})
      if presidio.get("pii_action") == "mask" and presidio.get("entities"):
          messages = await mask_pii_in_messages(messages, state["user_message"], ...)

      # Safety prefix (from Step 06) — if suspicious intent
      if state["risk_flags"].get("suspicious_intent"):
          messages = apply_safety_prefix(messages)
          messages = apply_spotlighting(messages)

      return {
          **state,
          "modified_messages": messages,
          "response_masked": bool(presidio.get("entities")),
      }
  ```

### 5. Dockerfile updates

- [ ] Ensure all dependencies installed:
  ```dockerfile
  # In builder stage
  RUN pip install --no-cache-dir . \
      && python -m spacy download en_core_web_lg
  ```
- [ ] Consider baking scanner warmup into image:
  ```dockerfile
  COPY scripts/warmup-scanners.py scripts/
  RUN python scripts/warmup-scanners.py
  ```
  → Adds ~1-2GB to image, but eliminates cold start latency

### 6. Performance benchmarks

- [ ] Measure and document:
  | Scanner | Cold start | Warm | Target |
  |---------|-----------|------|--------|
  | LLM Guard PromptInjection | ~3s | ~50-100ms | <200ms |
  | LLM Guard Toxicity | ~2s | ~30-60ms | <100ms |
  | LLM Guard Secrets | <100ms | <10ms | <50ms |
  | Presidio Analyzer | ~1s | ~20-50ms | <100ms |
  | **Parallel total (warm)** | — | **~100-150ms** | **<250ms** |
- [ ] If a scanner exceeds `scanner_timeout` → abort, log warning, continue

### 7. Tests

- [ ] `tests/test_parallel_scanners.py`:
  - Both scanners run concurrently → total time ≈ max, not sum
  - Scanner disabled by policy → results empty for that scanner
  - `fast` policy → no scanners execute
  - One scanner fails, other succeeds → merged results correct
- [ ] `tests/test_decision_with_scanners.py`:
  - Injection + balanced → BLOCK (risk > 0.7)
  - PII + strict (mask) → MODIFY
  - PII + paranoid (block) → BLOCK
  - Clean + all scanners pass → ALLOW
  - Toxic prompt above threshold → BLOCK
- [ ] `tests/test_integration_scanners.py` (end-to-end):
  - `POST /v1/chat/completions` injection → 403, `risk_flags.promptinjection`
  - `POST /v1/chat/completions` PII + strict → 200, `x-decision: MODIFY`
  - `POST /v1/chat/completions` clean → 200, `x-decision: ALLOW`
  - Verify request log in DB has scanner_results

---

## Definition of Done

- [ ] Scanners run **in parallel** via `asyncio.gather`
- [ ] Policy `config.nodes` controls which scanners are enabled
- [ ] `fast` policy → zero scanner overhead
- [ ] `calculate_risk_score()` uses scanner weights (injection×0.8, toxicity×0.5, etc.)
- [ ] PII + `pii_action=mask` → MODIFY → anonymized messages sent to LLM
- [ ] PII + `pii_action=block` → BLOCK (403)
- [ ] LangGraph: `parse → intent → rules → scanners → decision → ...`
- [ ] Scanner errors don't crash pipeline (logged, skipped)
- [ ] Warm scanner latency < 250ms (parallel)
- [ ] `pytest tests/` → all tests pass (unit + integration)
- [ ] `ruff check src/ tests/` → 0 errors
- [ ] Docker image builds with spaCy + LLM Guard dependencies
- [ ] All prior Step 04 + 06 tests still pass

---

| **Prev** | **Parent** |
|---|---|
| [07b — Presidio PII Node](07b-presidio.md) | [Step 07 — SPEC](SPEC.md) |
