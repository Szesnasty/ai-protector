# 02 — Compare Screen (`/red-team/compare`)

> **Layer:** Full-stack
> **Phase:** 3 (Proof & Conversion)
> **Depends on:** MVP complete, compare endpoint exists from Phase 1

## Scope

Full side-by-side comparison of two benchmark runs with category breakdown, score deltas, and fixed/new failures.

## Implementation Steps

### Step 1: Create route and page

- Route: `/red-team/compare?a=:id&b=:id`
- Run selectors: "Compare [Run #2 ▾] with [Run #3 ▾]"

### Step 2: Score delta display

- Side-by-side score badges with colored delta: ▲ +23 (green) or ▼ -5 (red)

### Step 3: Category breakdown comparison

- Table: Category | Before | After | Change
- Colored change indicators per category

### Step 4: Fixed / New failures

- **Fixed Failures**: scenarios that failed in Run A but pass in Run B
- **New Failures** (regressions): scenarios that passed in Run A but fail in Run B
- Each entry: scenario ID, title, status change

### Step 5: Validation rules

- Warning if different targets or packs
- Info notice if same pack but different `pack_version`

### Step 6: Export comparison report

- [Export Comparison Report] → JSON with both runs + deltas

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_compare_renders` | Page loads with two run summaries |
| `test_score_delta_correct` | Delta computed and colored correctly |
| `test_category_comparison` | Per-category changes shown |
| `test_fixed_failures_listed` | Fixed scenarios identified |
| `test_new_failures_listed` | Regressions identified |
| `test_different_pack_warning` | Warning shown for different packs |

## Definition of Done

- [ ] Full compare screen with side-by-side scores
- [ ] Category breakdown comparison
- [ ] Fixed/new failure lists
- [ ] Validation warnings for mismatched runs
- [ ] Export comparison report
- [ ] All tests pass
