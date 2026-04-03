# 06 — Markdown Export

> **Layer:** Backend
> **Phase:** 3 (Proof & Conversion)
> **Depends on:** JSON Export (Phase 3, step 01)

## Scope

Human-readable Markdown report for README, Confluence, or team sharing.

## Implementation Steps

### Step 1: Markdown template

- Report sections: Summary, Score, Category Breakdown, Top Failures, Run Info
- Clean formatting for GitHub/GitLab rendering

### Step 2: Export endpoint update

- `POST /v1/benchmark/runs/:id/export` with `{ format: "markdown" }`
- Returns `.md` file

### Step 3: Frontend format selector

- Dropdown on [Export Report]: JSON | Markdown

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_markdown_renders_correctly` | Valid Markdown output |
| `test_markdown_sections_complete` | All sections present |
| `test_format_selector_works` | Frontend switches between JSON/Markdown |

## Definition of Done

- [ ] Markdown export with all report sections
- [ ] Clean rendering on GitHub/Confluence
- [ ] Format selector in frontend
- [ ] All tests pass
