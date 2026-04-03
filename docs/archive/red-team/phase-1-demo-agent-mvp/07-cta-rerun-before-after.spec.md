# 07 — CTA + Re-run + Before/After

> **Layer:** Full-stack (Frontend + Backend)
> **Phase:** 1 (Demo Agent) — MVP
> **Depends on:** Results page (Phase 1, step 05), API compare endpoint

## Scope

The CTA section on the results page, the re-run flow, and the mini Before/After comparison. This is the **bridge** from "see problem" to "fix problem" — the conversion moment.

## Implementation Steps

### Step 1: CTA section — Variant A (Demo Agent)

For demo agent (already protected): the CTA focuses on policy optimization.

- "Want to improve this score?"
- "AI Protector detected N unprotected attack vectors. Apply recommended policies to harden your agent."
- Buttons:
  - [Apply Recommended Profile] — dialog: "Switch to Strict? Enables stricter thresholds." → apply
  - [Open Policies] → navigate to `/policies`
  - [Re-run with Strict Policy] → trigger new run with strict policy
  - [Export Report] → JSON download (Phase 1: minimal JSON)

### Step 2: "Apply Recommended Profile" flow

- Click → confirmation dialog with details of what changes
- On confirm → backend call to switch policy for demo agent
- Success → enable [Re-run] button with note "Policy changed to Strict"

### Step 3: Re-run benchmark

- [Re-run] creates a new benchmark with same target + pack + new policy
- POST `/v1/benchmark/runs` → navigate to `/red-team/run/{new_id}`
- After completion → results page with Before/After section

### Step 4: Mini Before/After comparison widget

- On results page: if a previous run exists for the same target, show:
  - "Before: 61/100 🟡 → After: 84/100 🟢 ▲ +23"
  - "2 failures fixed │ 1 still open │ 0 regressions"
  - [Full Comparison →] link (Phase 3 — disabled in Phase 1, or link to compare endpoint)

### Step 5: "Same target" detection

- Backend: query previous runs with same `target_type` + same `pack`
- Return `previous_run_id` in run details response (if exists)
- Frontend: if `previous_run_id` exists, fetch comparison data

### Step 6: JSON export (minimal)

- [Export Report] → calls `POST /v1/benchmark/runs/:id/export`
- Returns JSON file with: run metadata, score, category breakdown, all scenario results
- Download as `red-team-report-{run_id}.json`

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_cta_renders_for_demo` | CTA Variant A shown for demo agent |
| `test_apply_profile_dialog` | Dialog appears with policy change details |
| `test_apply_profile_calls_backend` | Confirm → backend request to change policy |
| `test_rerun_creates_new_run` | Re-run → POST → navigate to new run |
| `test_before_after_appears` | Second run shows Before/After widget |
| `test_before_after_score_delta` | Delta computed correctly |
| `test_before_after_hidden_first_run` | First run — no Before/After |
| `test_export_json_downloads` | Export → JSON file downloaded |
| `test_export_contains_all_data` | JSON has run metadata, scores, scenario results |

## Definition of Done

- [ ] CTA Variant A renders with all buttons for demo agent
- [ ] Apply Recommended Profile → changes policy → enables re-run
- [ ] Re-run creates new benchmark and navigates to progress
- [ ] Mini Before/After appears on second run with correct delta
- [ ] JSON export works with full data
- [ ] The full loop works: run → see score → apply fix → re-run → see improvement
- [ ] All tests pass
