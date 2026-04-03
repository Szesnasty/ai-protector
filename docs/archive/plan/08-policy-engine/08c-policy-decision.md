# 08c — Policy-Aware Decision Node

| | |
|---|---|
| **Parent** | [Step 08 — Policy Engine](SPEC.md) |
| **Prev sub-step** | [08b — Policy Validation & Seed Update](08b-policy-validation.md) |
| **Estimated time** | 2–2.5 hours |

---

## Goal

Make the `DecisionNode` fully policy-aware: dynamic threshold resolution from policy config, policy-level risk score weights, and ensure Redis cache invalidation works end-to-end after CRUD mutations.

---

## Tasks

### 1. Dynamic threshold resolution in DecisionNode

- [x] Replace hardcoded weights with policy-configurable values:
  ```python
  def calculate_risk_score(state: PipelineState) -> float:
      thresholds = state.get("policy_config", {}).get("thresholds", {})

      # Scanner weights (configurable per policy)
      injection_weight = thresholds.get("injection_weight", 0.8)
      toxicity_weight = thresholds.get("toxicity_weight", 0.5)
      secrets_weight = thresholds.get("secrets_weight", 0.6)
      pii_per_entity = thresholds.get("pii_per_entity_weight", 0.1)
      pii_max = thresholds.get("pii_max_weight", 0.5)

      # ... apply weights ...
  ```

- [x] Support optional `weight_overrides` in policy config:
  ```json
  {
    "thresholds": {
      "max_risk": 0.5,
      "injection_weight": 0.9,
      "toxicity_weight": 0.7
    }
  }
  ```

### 2. Policy-level decision customization

- [x] `fast` policy behavior:
  - Higher `max_risk` (0.9) — only blocks obvious attacks
  - No scanner flags (scanners don't run at all)
  - Only rule-based + intent-based scoring

- [x] `balanced` policy behavior:
  - Standard `max_risk` (0.7)
  - LLM Guard flags contribute to score
  - PII flagged but not blocked

- [x] `strict` policy behavior:
  - Lower `max_risk` (0.5)
  - PII → mask (MODIFY decision forced)
  - All scanner flags contribute

- [x] `paranoid` policy behavior:
  - Lowest `max_risk` (0.3)
  - PII → block (BLOCK decision forced)
  - All scanner flags contribute with higher weights

### 3. Redis cache invalidation end-to-end

- [x] Verify that after `PATCH /v1/policies/{id}`:
  1. Redis key `policy_config:{name}` is deleted
  2. Next `run_pipeline()` call fetches fresh config from DB
  3. Pipeline uses updated thresholds

- [x] Add cache invalidation to `DELETE` endpoint too
- [x] Consider adding `Cache-Control` header to policy endpoints

### 4. Policy selection in runner

- [x] Verify `run_pipeline()` and `run_pre_llm_pipeline()` use latest config:
  ```python
  async def run_pipeline(...):
      policy_config = await get_policy_config(policy_name)
      # policy_config now comes from DB/Redis with real thresholds
  ```

- [x] Log policy version used:
  ```python
  logger.info("pipeline_complete",
      request_id=request_id,
      policy=policy_name,
      policy_version=policy_config.get("_version"),  # if tracked
      decision=...,
  )
  ```

### 5. Tests

- [x] `test_decision_fast_policy` — high max_risk → fewer blocks
- [x] `test_decision_balanced_policy` — standard thresholds
- [x] `test_decision_strict_policy` — low max_risk, PII mask
- [x] `test_decision_paranoid_policy` — lowest max_risk, PII block
- [x] `test_custom_weights` — custom injection_weight applied
- [x] `test_cache_invalidation_e2e` — update policy → next request uses new config
- [x] `test_default_thresholds` — missing thresholds → sensible defaults

---

## Definition of Done

- [x] `calculate_risk_score()` uses policy-configurable weights
- [x] All 4 policy levels produce correct decisions for identical inputs
- [x] Custom weight overrides in policy config are respected
- [x] Redis cache invalidated on CRUD → next request picks up changes
- [x] Pipeline runner logs policy version
- [x] All tests pass
- [x] `ruff check src/ tests/` → 0 errors

---

| **Prev** | **Parent** |
|---|---|
| [08b — Policy Validation & Seed Update](08b-policy-validation.md) | [Step 08 — SPEC](SPEC.md) |
