# 01 — Full Suite Pack

> **Layer:** Backend
> **Phase:** 4 (Advanced)
> **Depends on:** Core Security + Agent Threats packs finalized

## Scope

Combined pack with all scenarios from Core Security and Agent Threats. Provides the most comprehensive benchmark.

## Implementation Steps

### Step 1: Pack definition

- `full_suite.yaml` combining all scenarios
- Proper deduplication (no overlapping IDs)
- Updated `scenario_count` and `applicable_to`

### Step 2: Automatic assembly

- Option: generate Full Suite from existing packs at load time (union)
- Or: maintain as a separate curated file

### Step 3: Frontend visibility

- Show Full Suite as a pack option on configure screen
- Remove "Iteration 3+" badge

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_full_suite_loads` | Pack loads and validates |
| `test_no_duplicate_ids` | No scenario ID conflicts |
| `test_full_suite_count` | Scenario count matches sum |

## Definition of Done

- [ ] Full Suite pack available and loadable
- [ ] All scenarios from both packs included
- [ ] Frontend shows pack option
- [ ] All tests pass
