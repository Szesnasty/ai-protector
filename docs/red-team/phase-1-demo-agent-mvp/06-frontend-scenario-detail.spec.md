# 06 — Frontend Scenario Detail (`/red-team/results/:id/scenario/:sid`)

> **Layer:** Frontend (Nuxt 3 + Vuetify 3)
> **Phase:** 1 (Demo Agent) — MVP
> **Depends on:** Scenario detail endpoint (Phase 1, step 01)

## Scope

Detailed view of a single scenario result. The user comes here to understand ONE problem: what was the attack, why it got through, and how to fix it.

> **UX rule:** This page answers 3 questions: What was the attack? → Why did it get through? → How do I fix it? Technical pipeline details are available but hidden by default.

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

### Step 4: Result summary (always visible)

- Clear one-line result: "ALLOWED — this attack got through" or "BLOCKED — your agent stopped this"
- No raw pipeline decision in the main view

### Step 5: "Why it got through" section (always visible)

- Static text from scenario metadata (`why_it_passes` field)
- Written in **plain language** — should feel like a teammate explaining the problem
- If null → section not displayed
- Example: "The attack uses indirect instruction injection disguised as a 'maintenance mode' request. The prompt doesn't contain blocked keywords and slips under the scanner thresholds."

### Step 6: "How to fix it" section (always visible)

- List of actionable fixes from `fix_hints`
- Each fix is a deep link to a concrete action:
  - "Switch to Strict policy" → `/policies`
  - "Block pattern X" → `/security-rules/new?pattern=X`
- **Rule:** if no concrete fix exists, section is hidden (no vague advice)

### Step 7: Technical Details section (collapsible, collapsed by default)

- Full pipeline decision:
  - Decision: ALLOW/BLOCK
  - Intent: conversation / tool_call
  - Risk Score: 0.38
  - Flags: []
  - Scanner Results (list): each scanner + result + score
- LLM Guard threshold, Presidio entities, etc.
- This section is for security engineers who want to dig deeper — not for the main flow

### Step 7: Navigation

- [← Back to Results] button → `/red-team/results/:id`
- Possibly prev/next scenario navigation

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_page_renders_scenario` | Detail page shows scenario data |
| `test_attack_prompt_displayed` | Full prompt shown in code block |
| `test_result_summary_visible` | "ALLOWED/BLOCKED" summary always visible |
| `test_why_it_got_through_shown` | Plain language explanation rendered when available |
| `test_why_it_got_through_hidden_when_null` | No section when `why_it_passes` is null |
| `test_fix_hints_as_links` | Fix hints render as clickable deep links |
| `test_no_fixes_hides_section` | No `fix_hints` → section hidden |
| `test_technical_details_collapsed` | Pipeline decision hidden in collapsed section by default |
| `test_technical_details_expandable` | Clicking "Technical Details" reveals scanner results |
| `test_back_button_navigates` | [← Back] → results page |
| `test_copy_prompt_button` | Copy button copies prompt text |

## Definition of Done

- [ ] Scenario detail page renders all fields
- [ ] Attack prompt displayed in code block with copy
- [ ] Result summary shows clear ALLOWED/BLOCKED verdict
- [ ] "Why it got through" shows plain language explanation (hidden when null)
- [ ] Fix hints render as deep links to concrete actions
- [ ] Pipeline decision/scanner results in **collapsible Technical Details** section (collapsed by default)
- [ ] Back navigation works
- [ ] All tests pass
