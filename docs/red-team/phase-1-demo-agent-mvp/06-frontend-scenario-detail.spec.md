# 06 — Frontend Scenario Detail (`/red-team/results/:id/scenario/:sid`)

> **Layer:** Frontend (Nuxt 3 + Vuetify 3)
> **Phase:** 1 (Demo Agent) — MVP
> **Depends on:** Scenario detail endpoint (Phase 1, step 01)

## Scope

Detailed view of a single scenario result. Shows: attack prompt, pipeline decision, scanner results, why it passed/failed, and suggested fix with actionable deep links.

## Implementation Steps

### Step 1: Create route and page component

- Route: `/red-team/results/:id/scenario/:sid`
- Page: `app/pages/red-team/results/[id]/scenario/[sid].vue`
- Fetch: `GET /v1/benchmark/runs/:id/scenarios/:sid`

### Step 2: Header section

- Scenario ID + title (e.g., "CS-012 — System prompt extraction")
- Status icon (❌ fail, ✅ pass, ⚠️ false positive)
- Category, Expected vs Actual, Latency

### Step 3: Attack prompt display

- Code block showing the full attack prompt
- Monospace font, syntax-highlighted if applicable
- Copy button

### Step 4: Pipeline decision display

- Structured view of the pipeline result:
  - Decision: ALLOW/BLOCK
  - Intent: conversation / tool_call
  - Risk Score: 0.38
  - Flags: []
  - Scanner Results (list): each scanner + result + score

### Step 5: "Why it passed/failed" section

- Static text from scenario metadata (`why_it_passes` field)
- If null → section not displayed
- Clear, human-readable explanation

### Step 6: "Suggested fix" section

- List of actionable fixes from `fix_hints`
- Each fix is a deep link to a concrete action:
  - "Switch to Strict policy" → `/policies`
  - "Block pattern X" → `/security-rules/new?pattern=X`
  - "Lower threshold to Y" → `/settings/scanners`
- **Rule:** if no concrete fix exists, section is hidden (no vague advice)

### Step 7: Navigation

- [← Back to Results] button → `/red-team/results/:id`
- Possibly prev/next scenario navigation

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_page_renders_scenario` | Detail page shows scenario data |
| `test_attack_prompt_displayed` | Full prompt shown in code block |
| `test_pipeline_decision_displayed` | Scanner results visible |
| `test_why_it_passed_shown` | Explanation text rendered when available |
| `test_why_it_passed_hidden_when_null` | No section when `why_it_passes` is null |
| `test_fix_hints_as_links` | Fix hints render as clickable deep links |
| `test_no_fixes_hides_section` | No `fix_hints` → section hidden |
| `test_back_button_navigates` | [← Back] → results page |
| `test_copy_prompt_button` | Copy button copies prompt text |

## Definition of Done

- [ ] Scenario detail page renders all fields
- [ ] Attack prompt displayed in code block with copy
- [ ] Pipeline decision with scanner results displayed
- [ ] "Why it passed" shows static explanation (hidden when null)
- [ ] Fix hints render as deep links to concrete actions
- [ ] Back navigation works
- [ ] All tests pass
