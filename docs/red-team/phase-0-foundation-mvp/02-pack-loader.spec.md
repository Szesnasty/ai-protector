# 02 — Pack Loader

> **Module:** `red-team/packs/`
> **Phase:** 0 (Foundation) — MVP
> **Depends on:** Scenario Schema (`red-team/schemas/`)

## Scope

Loads scenario packs from YAML/JSON files, validates them against the schema, and filters scenarios based on target configuration.

## Implementation Steps

### Step 1: Pack file discovery

- Scan `packs/` directory for `.yaml` / `.json` files
- Each file is one pack (e.g., `core_security.yaml`, `agent_threats.yaml`)
- Return list of available pack names + metadata (name, version, scenario_count)

### Step 2: Pack loading + validation

- Read pack file → parse YAML/JSON → validate against `Pack` Pydantic model
- On validation failure → raise `PackLoadError` with file path + details
- Cache loaded packs in memory (they're static per deployment)

### Step 3: Scenario filtering pipeline

Apply filters in order, tagging each skipped scenario with a reason:

1. **Target type filter**: skip if `scenario.applicable_to` doesn't include `target_config.agent_type`
   - Skip reason: `not_applicable`
2. **Safe mode filter**: skip if `safe_mode = true` AND `scenario.mutating = true`
   - Skip reason: `safe_mode`
3. **Detector availability filter**: skip if `detector.type` not registered in engine
   - Skip reason: `detector_unavailable`

Return: `FilteredPack { scenarios: list[Scenario], skipped: list[SkippedScenario] }`

### Step 4: Create the Core Security pack (10–15 strong scenarios)

Write the actual `core_security.yaml` with real attack scenarios. Quality > quantity.

Scenario categories (mapping to MVP buckets):
- **Prompt Injection / Jailbreak**: basic injection, DAN, role-play jailbreak, system prompt override, multi-turn escalation
- **Data Leakage / PII**: system prompt extraction, PII extraction, context leak, forbidden data in response

Each scenario must have:
- A deterministic detector (no `llm_judge`)
- A clear `fix_hints` list
- Appropriate `severity` and `mutating` flags

### Step 5: Create the Agent Threats pack placeholder

- Stub `agent_threats.yaml` with 3–5 example scenarios
- Mark as `applicable_to: ["tool_calling"]`
- This pack is not fully developed until Phase 3+, but the loader should handle it

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_load_valid_pack` | A well-formed pack loads without errors |
| `test_load_invalid_pack_raises` | Malformed pack raises `PackLoadError` |
| `test_list_available_packs` | Returns names + metadata of all packs in directory |
| `test_filter_by_target_type` | `chatbot_api` target skips `tool_calling`-only scenarios |
| `test_filter_by_safe_mode` | Safe mode skips mutating scenarios |
| `test_filter_by_detector_availability` | Scenarios with unregistered detectors are skipped |
| `test_skipped_reasons_are_correct` | Each skipped scenario has the right `skipped_reason` |
| `test_filter_preserves_order` | Filtering doesn't reorder scenarios |
| `test_core_security_pack_loads` | The real `core_security.yaml` passes validation |
| `test_core_security_scenarios_deterministic` | All Core Security scenarios use Priority 1 detectors |
| `test_scenario_quality_gate` | Every scenario has non-empty `prompt`, `description`, `fix_hints` |

## Definition of Done

- [ ] Pack Loader loads and validates YAML/JSON packs
- [ ] Filtering pipeline applies all 3 rules in order with correct skip reasons
- [ ] `core_security.yaml` contains 10–15 strong, deterministic scenarios
- [ ] `agent_threats.yaml` stub exists and loads
- [ ] All tests pass, >90% coverage
- [ ] No imports from other red-team modules except `schemas/`
