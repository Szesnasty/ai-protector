# 04 — Frontend Progress (`/red-team/run/:id`)

> **Layer:** Frontend (Nuxt 3 + Vuetify 3)
> **Phase:** 1 (Demo Agent) — MVP
> **Depends on:** SSE endpoint (Phase 1, step 01)

## Scope

Live progress screen showing benchmark execution in real-time via SSE.

## Implementation Steps

### Step 1: Create route and page component

- Route: `/red-team/run/:id`
- Page: `app/pages/red-team/run/[id].vue`

### Step 2: Implement SSE connection

- Connect to `GET /v1/benchmark/runs/:id/progress`
- Parse SSE events (`scenario_start`, `scenario_complete`, `scenario_skipped`, `run_complete`, `run_failed`, `run_cancelled`)
- Reactive state: scenarios list, progress counter, elapsed time

### Step 3: Progress bar

- Linear progress bar: `completed / total`
- Percentage label: "18/30 (60%)"
- Elapsed time counter (updates every second)
- Estimated remaining time (based on average scenario latency)

### Step 4: Live feed list

- Scrollable list of scenario results
- Each row: icon (✅/❌/⚠️/🔄) + scenario ID + title + result + latency
- New results appear at bottom, auto-scroll
- Currently running scenario: 🔄 with "Running: CS-018 — Social engineering pretexting"

### Step 5: Header info bar

- "Target: Demo Agent │ Pack: Core Security │ 30 attacks"
- Title: "Benchmark Running..."

### Step 6: [Cancel] button

- DELETE `/v1/benchmark/runs/:id`
- Confirmation dialog: "Cancel this benchmark? Partial results will be saved."
- After cancel → navigate to results page with partial results

### Step 7: Auto-redirect on completion

- On `run_complete` event → navigate to `/red-team/results/:id`
- Small delay (1s) for the user to see "Complete!" animation

### Step 8: Handle disconnection

- If SSE connection drops → show reconnection banner
- Poll run status as fallback: `GET /v1/benchmark/runs/:id`
- If run already completed → redirect to results

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_page_renders_with_progress` | Progress page shows bar and feed |
| `test_sse_events_update_ui` | Scenario events update the live feed |
| `test_progress_bar_updates` | Progress bar moves with each completed scenario |
| `test_cancel_button_works` | Cancel → confirmation → DELETE → redirect |
| `test_auto_redirect_on_complete` | run_complete event → navigate to results |
| `test_elapsed_time_ticks` | Timer updates every second |
| `test_reconnection_on_disconnect` | SSE drop → reconnect banner |

## Definition of Done

- [ ] SSE connection receives and processes all event types
- [ ] Progress bar, live feed, elapsed time all update in real-time
- [ ] Cancel button works with confirmation
- [ ] Auto-redirect to results on completion
- [ ] Handles SSE disconnection gracefully
- [ ] All tests pass
