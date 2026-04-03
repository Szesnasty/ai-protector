# 02 — Pack Loader

> **Module:** `red-team/packs/`
> **Phase:** 0 (Foundation) — MVP
> **Depends on:** Scenario Schema (`red-team/schemas/`)
> **Updated:** 2026-03-24 — final source of truth for contracts

## Scope

Loads scenario packs from YAML/JSON files, validates them against the schema, and filters scenarios based on target configuration. Returns a `FilteredPack` with explicit counting of total/applicable/skipped scenarios.

---

## Input / Output Contracts

### Input: `PackLoadRequest`

```python
@dataclass
class PackLoadRequest:
    pack_name: str              # "core_security" | "agent_threats"
    target_config: TargetConfig # From the run configuration

@dataclass
class TargetConfig:
    agent_type: str             # "chatbot_api" | "tool_calling"
    safe_mode: bool             # True = skip mutating scenarios
    # Other fields (url, auth, etc.) not relevant to Pack Loader
```

### Output: `FilteredPack`

```python
@dataclass
class FilteredPack:
    pack_name: str
    pack_version: str                    # Semver, e.g. "1.0.0"
    total_in_pack: int                   # Total scenarios in the pack file (before filtering)
    total_applicable: int                # After filtering — this is the denominator for scoring
    skipped_count: int                   # total_in_pack - total_applicable
    skipped_reasons: dict[str, int]      # {"safe_mode": 5, "not_applicable": 2, "detector_unavailable": 1}
    scenarios: list[Scenario]            # Scenario objects that will be executed
    skipped: list[SkippedScenario]       # Scenario objects that were filtered out

@dataclass
class SkippedScenario:
    scenario_id: str
    title: str
    reason: str                          # "not_applicable" | "safe_mode" | "detector_unavailable"
```

### Output: `PackInfo` (for pack listing)

```python
@dataclass
class PackInfo:
    name: str                            # "core_security"
    display_name: str                    # "Core Security"
    description: str                     # User-facing description (no jargon)
    version: str                         # Semver
    scenario_count: int                  # Total in pack
    applicable_to: list[str]             # ["chatbot_api", "tool_calling"]
    default_for: list[str]               # ["chatbot_api"] — auto-selected for this type
```

---

## Implementation Steps

### Step 1: Pack file discovery

- Scan `packs/` directory for `.yaml` / `.json` files
- Each file is one pack (e.g., `core_security.yaml`, `agent_threats.yaml`)
- `list_packs() → list[PackInfo]` — returns metadata for all available packs
- Pack metadata is at the top of each file (not computed from scenarios)

### Step 2: Pack loading + validation

- `load_pack(pack_name) → Pack` — read file, parse, validate against Pydantic model
- On validation failure → raise `PackLoadError` with file path + details
- Cache loaded packs in memory (they're static per deployment)
- Validate invariants:
  - `pack.scenario_count == len(pack.scenarios)`
  - All `scenario.id` values unique within pack
  - Every `detector.type` is in the `DetectorType` enum

### Step 3: Scenario filtering pipeline

`filter_pack(pack: Pack, config: TargetConfig, available_detectors: set[str]) → FilteredPack`

Apply filters in order, tagging each skipped scenario with a reason:

1. **Target type filter**: skip if `scenario.applicable_to` doesn't include `config.agent_type`
   - Skip reason: `not_applicable`
2. **Safe mode filter**: skip if `config.safe_mode = true` AND `scenario.mutating = true`
   - Skip reason: `safe_mode`
3. **Detector availability filter**: skip if `scenario.detector.type` not in `available_detectors`
   - Skip reason: `detector_unavailable`

Build and return `FilteredPack` with:
- `total_in_pack = len(pack.scenarios)`
- `total_applicable = len(filtered_scenarios)`
- `skipped_count = total_in_pack - total_applicable`
- `skipped_reasons = count per reason`

### Step 4: Counting invariants (hard rules)

These must always hold:
```python
assert pack.total_in_pack == len(pack.scenarios) + len(pack.skipped)
assert pack.total_applicable == len(pack.scenarios)
assert pack.skipped_count == len(pack.skipped)
assert pack.skipped_count == sum(pack.skipped_reasons.values())
```

The Run Engine uses `total_applicable` as the denominator for progress (e.g., "18/22") and scoring.

### Step 5: Create the Core Security pack (10–15 strong scenarios)

Write the actual `core_security.yaml` with real attack scenarios. Quality > quantity.

Scenario categories (mapping to the 4 canonical MVP buckets):
- **Prompt Injection / Jailbreak**: basic injection, DAN, role-play jailbreak, system prompt override, multi-turn escalation
- **Data Leakage / PII**: system prompt extraction, PII extraction, context leak, forbidden data in response

Each scenario must have:
- A deterministic detector (no `llm_judge`)
- A clear `fix_hints` list (with deep link templates)
- Appropriate `severity` and `mutating` flags
- `why_it_passes` field populated (plain language, no jargon)

### Step 6: Create the Agent Threats pack placeholder

- Stub `agent_threats.yaml` with 3–5 example scenarios
- Mark as `applicable_to: ["tool_calling"]`
- Categories: Tool Abuse, Access Control
- This pack is not fully developed until Phase 3+, but the loader should handle it

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_load_valid_pack` | A well-formed pack loads without errors |
| `test_load_invalid_pack_raises` | Malformed pack raises `PackLoadError` |
| `test_list_available_packs` | Returns `PackInfo` for all packs in directory |
| `test_filter_by_target_type` | `chatbot_api` target skips `tool_calling`-only scenarios |
| `test_filter_by_safe_mode` | Safe mode skips mutating scenarios |
| `test_filter_by_detector_availability` | Scenarios with unregistered detectors are skipped |
| `test_skipped_reasons_are_correct` | Each skipped scenario has the right `reason` |
| `test_skipped_reasons_breakdown` | `skipped_reasons` dict sums correctly |
| `test_counting_invariants` | `total_in_pack = total_applicable + skipped_count` always holds |
| `test_filter_preserves_order` | Filtering doesn't reorder scenarios |
| `test_core_security_pack_loads` | The real `core_security.yaml` passes validation |
| `test_core_security_scenarios_deterministic` | All Core Security scenarios use Priority 1 detectors |
| `test_scenario_quality_gate` | Every scenario has non-empty `prompt`, `description`, `fix_hints`, `why_it_passes` |
| `test_pack_info_display_name` | `list_packs()` returns display names (not internal keys) |

## Definition of Done

- [ ] Pack Loader loads and validates YAML/JSON packs
- [ ] `FilteredPack` output includes `total_in_pack`, `total_applicable`, `skipped_count`, `skipped_reasons`
- [ ] Counting invariants enforced (total_in_pack = applicable + skipped)
- [ ] Filtering pipeline applies all 3 rules in order with correct skip reasons
- [ ] `list_packs()` returns `PackInfo` with user-facing display names and descriptions
- [ ] `core_security.yaml` contains 10–15 strong, deterministic scenarios
- [ ] Every scenario has `fix_hints` and `why_it_passes` populated
- [ ] `agent_threats.yaml` stub exists and loads
- [ ] All tests pass, >90% coverage
- [ ] No imports from other red-team modules except `schemas/`
