# 05 — Scenarios Browser

> **Layer:** Full-stack
> **Phase:** 4 (Advanced)
> **Depends on:** Pack Loader, Scenario Schema

## Scope

Browse individual attack scenarios: search, filter by category/severity/pack, and run ad-hoc against a target.

## Implementation Steps

### Step 1: Scenarios list page

- Route: `/red-team/scenarios`
- Tab inside Red Team section (alongside Benchmark Runs)
- Table: ID, Title, Category, Severity, Pack, Mutating, Detector Type

### Step 2: Search and filter

- Text search on title/description
- Filter by: category, severity, pack, mutating, detector type
- Sort by any column

### Step 3: Scenario detail view

- Click → expanded view with full prompt, detector config, fix hints
- Preview of what this scenario tests

### Step 4: Ad-hoc run (single scenario)

- [Run This Scenario] button on detail view
- Select target → send prompt → see result immediately
- Lightweight — no full benchmark run needed

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_scenarios_list_loads` | All scenarios from all packs listed |
| `test_filter_by_category` | Filter narrows results |
| `test_search_by_title` | Search finds matching scenarios |
| `test_adhoc_run` | Single scenario runs against target |

## Definition of Done

- [ ] Scenarios browser with search and filters
- [ ] Detail view with full scenario information
- [ ] Ad-hoc single-scenario run
- [ ] All tests pass
