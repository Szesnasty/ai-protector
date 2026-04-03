# 03 — Recent Runs

> **Layer:** Full-stack
> **Phase:** 3 (Proof & Conversion)
> **Depends on:** MVP complete, list runs endpoint

## Scope

"Recent Runs" section on the `/red-team` landing page showing previous benchmark runs with scores and quick actions.

## Implementation Steps

### Step 1: Fetch recent runs

- Call `GET /v1/benchmark/runs?limit=10` on page load
- Display as table/list: Run #, Target, Score, Time, [View]

### Step 2: UI table

- Columns: Run # | Target | Pack | Score (with badge color) | Time (relative) | [View]
- [View] → navigate to `/red-team/results/:id`
- Empty state (no runs): "No benchmark runs yet. Start one above!"

### Step 3: Auto-update

- New run completes → appears in list (poll or SSE)

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_recent_runs_displayed` | Runs shown in table |
| `test_empty_state` | No runs → placeholder |
| `test_view_navigates` | [View] → results page |
| `test_score_badge_in_list` | Score shows with color |

## Definition of Done

- [ ] Recent Runs section on landing page
- [ ] Shows last 10 runs with score badges
- [ ] Empty state handled
- [ ] All tests pass
