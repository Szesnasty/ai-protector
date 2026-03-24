# 01 — Scenario Schema

> **Module:** `red-team/schemas/`
> **Phase:** 0 (Foundation) — MVP
> **Depends on:** Nothing

## Scope

Pure data validation — Pydantic models that define the canonical scenario format. No I/O, no side effects.

## Implementation Steps

### Step 1: Define core Pydantic models

- `Scenario` model with all fields from the spec:
  - `id`, `title`, `category`, `severity`, `mutating`, `applicable_to`, `tags`
  - `prompt`, `expected` (enum: BLOCK | ALLOW | MODIFY)
  - `detector` (nested: `type` + `config`)
  - `fix_hints`, `description`, `why_it_passes`
- `DetectorConfig` model (base) with `type` field validated against `DetectorType` enum
- `Pack` model: `name`, `version`, `description`, `scenario_count`, `applicable_to`, `scenarios[]`

### Step 2: Define enums

- `DetectorType` enum: `exact_match`, `regex`, `keyword`, `refusal_pattern`, `json_assertion`, `tool_call_detect`, `heuristic`, `llm_judge`
- `Severity` enum: `critical`, `high`, `medium`, `low`
- `ExpectedAction` enum: `BLOCK`, `ALLOW`, `MODIFY`
- `AgentType` enum: `chatbot_api`, `tool_calling`
- `Category` enum (MVP 4 buckets): `prompt_injection_jailbreak`, `data_leakage_pii`, `tool_abuse`, `access_control`

### Step 3: Define per-detector config schemas

- `RegexDetectorConfig`: `pattern`, `match_means` (fail/pass)
- `KeywordDetectorConfig`: `keywords[]`, `match_means`, `case_sensitive`
- `RefusalPatternConfig`: `refusal_phrases[]`, `min_match`, `match_means`
- `JsonAssertionConfig`: `path`, `expected`
- `ToolCallDetectConfig`: `tool_names[]`, `invoked_means`
- `ExactMatchConfig`: `forbidden_strings[]`, `match_means`
- `HeuristicConfig`: `checks[]`, `fail_threshold`

### Step 4: Add pack-level validation

- `scenario_count` must match `len(scenarios)`
- All `scenario.id` values must be unique within a pack
- Every `detector.type` must be in `DetectorType` enum
- `applicable_to` on pack level must be superset of each scenario's `applicable_to`

### Step 5: Define `RawTargetResponse` dataclass

```python
@dataclass
class RawTargetResponse:
    status_code: int
    headers: dict[str, str]
    body_text: str
    parsed_json: dict | None
    tool_calls: list[ToolCall] | None
    latency_ms: int

@dataclass
class ToolCall:
    name: str
    arguments: dict
    result: str | None
```

### Step 6: Define `EvalResult` dataclass

```python
@dataclass
class EvalResult:
    passed: bool
    actual: str       # "BLOCK" | "ALLOW" | "MODIFY"
    detail: str       # Human-readable explanation
    confidence: float # 1.0 for deterministic, <1.0 for heuristic
```

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_valid_scenario_parses` | A correctly-formed scenario YAML/dict passes validation |
| `test_invalid_detector_type_rejected` | Unknown detector type raises `ValidationError` |
| `test_invalid_severity_rejected` | Unknown severity raises `ValidationError` |
| `test_scenario_count_mismatch_fails` | Pack with wrong `scenario_count` fails validation |
| `test_duplicate_scenario_ids_fails` | Pack with duplicate IDs fails validation |
| `test_each_detector_config_validates` | Each detector type's config schema validates correctly |
| `test_raw_target_response_creation` | `RawTargetResponse` can be constructed with all fields |
| `test_eval_result_creation` | `EvalResult` can be constructed and fields are accessible |
| `test_category_enum_covers_mvp_buckets` | All 4 MVP categories exist in the enum |

## Definition of Done

- [ ] All Pydantic models defined and importable from `red-team/schemas/__init__.py`
- [ ] All enums defined and exported
- [ ] `RawTargetResponse` and `EvalResult` dataclasses defined
- [ ] Pack validation catches all invalid states with clear error messages
- [ ] 100% test coverage on schema module (pure validation = easy to cover)
- [ ] No I/O, no imports from other red-team modules
