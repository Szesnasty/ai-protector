# 02 — JailbreakBench Pack (NeurIPS 2024)

> **Layer:** Backend
> **Phase:** 4 (Advanced)
> **Depends on:** Pack Loader, Evaluator Engine

## Scope

Integration of the JailbreakBench academic dataset — real jailbreaks from research papers. ~100 attack scenarios.

## Implementation Steps

### Step 1: Dataset import

- Source: JailbreakBench (NeurIPS 2024 benchmark)
- Convert academic format → our scenario schema
- Map to appropriate categories and severities

### Step 2: Detector assignment

- Assign deterministic detectors where possible
- Heuristic detectors for edge cases
- Document where LLM-judge would improve accuracy (future)

### Step 3: Attribution and licensing

- Proper attribution in pack metadata
- License compliance

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_jailbreakbench_loads` | Pack loads and validates |
| `test_all_scenarios_have_detectors` | No scenarios missing detector config |
| `test_attribution_present` | Pack metadata includes source attribution |

## Definition of Done

- [ ] JailbreakBench pack converted and loadable
- [ ] All scenarios have assigned detectors
- [ ] Attribution and licensing compliant
- [ ] All tests pass
