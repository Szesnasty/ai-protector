# 04 — Weighted Scoring UI

> **Layer:** Full-stack
> **Phase:** 3 (Proof & Conversion)
> **Depends on:** Score Calculator (Phase 0 — already computing weighted), Results page (Phase 1)

## Scope

Switch the displayed score from `score_simple` to `score_weighted`. Both have been computed and stored since Phase 0.

## Implementation Steps

### Step 1: Switch backend `score` field

- Change: `score = score_weighted` (was `score_simple`)
- All API responses use the `score` field → no frontend logic changes needed

### Step 2: Score breakdown display

- Show below the score badge: "+42 passed −18 critical fails −3 minor fails = 61/100"
- Requires: scenario results with severity weights

### Step 3: Historical consistency

- Old runs already have `score_weighted` stored
- No recalculation needed — just swap which field `score` points to

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_score_field_is_weighted` | API returns `score = score_weighted` |
| `test_score_breakdown_displayed` | Breakdown text shown on results page |
| `test_old_runs_consistent` | Historical runs show correct weighted score |

## Definition of Done

- [ ] `score` field switched to weighted
- [ ] Score breakdown displayed in UI
- [ ] Historical runs unaffected
- [ ] All tests pass
