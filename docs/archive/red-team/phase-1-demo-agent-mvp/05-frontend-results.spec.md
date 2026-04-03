# 05 — Frontend Results (`/red-team/results/:id`)

> **Layer:** Frontend (Nuxt 3 + Vuetify 3)
> **Phase:** 1 (Demo Agent) — MVP
> **Depends on:** Run details + scenario list endpoints (Phase 1, step 01)

## Scope

The most important screen — score badge, category breakdown, top failures, and CTA. This is where the user understands their security posture.

## Implementation Steps

### Step 1: Create route and page component

- Route: `/red-team/results/:id`
- Page: `app/pages/red-team/results/[id].vue`
- Fetch run details: `GET /v1/benchmark/runs/:id`
- Fetch scenario results: `GET /v1/benchmark/runs/:id/scenarios`

### Step 2: Hero section — Score badge

- Large circular score badge (0–100) with color:
  - 0–39: red (Critical)
  - 40–59: orange (Weak)
  - 60–79: yellow (Needs Hardening)
  - 80–89: green (Good)
  - 90–100: dark green (Strong)
- Below badge: label ("Needs Hardening")
- Summary line: "3 critical gaps │ 27 attacks blocked │ 30 tested"
- **No scoring formula visible.** No "+42 passed −18 critical fails". Just the score, label, and simple counts.
- Optional: collapsible "Score details" for advanced users (scoring breakdown, weighted formula)

### Step 3: Category breakdown section

- Horizontal bar charts for each category
- Each bar: category name + filled/empty segments + percentage
- MVP categories: Prompt Injection/Jailbreak, Data Leakage/PII (Core Security)
- When Agent Threats pack is used: also Tool Abuse, Access Control
- Bars sorted by score ascending (worst first — draws attention)

### Step 4: Top failures section

- List of max 3–5 failed scenarios, sorted by severity weight (critical first)
- Keep the list short — user reads top 3, not top 10
- Each entry: scenario ID, title, "Expected: BLOCK → Got: ALLOW", category
- [View Details] link → navigates to scenario detail page

### Step 5: Confidence banner (for demo agent = High)

- For High confidence: no banner needed (don't add noise when everything is fine)
- For Medium confidence (future phases): use positive framing:
  - ℹ️ "External scan — based on response analysis. For deeper analysis, route traffic through AI Protector proxy."
  - NOT: "Assessment confidence: Medium — Heuristic scan"
  - Frame as upgrade path, not a disclaimer of unreliability

### Step 6: Header info bar

- "Target: Demo Agent │ Pack: Core Security │ 1 min ago"

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_page_renders_with_score` | Score badge displays correct value and color |
| `test_score_badge_color_ranges` | Each range maps to correct color |
| `test_category_breakdown_rendered` | Category bars display with percentages |
| `test_top_failures_sorted_by_severity` | Critical failures appear first |
| `test_view_details_navigates` | Click [View Details] → scenario detail page |
| `test_confidence_badge_high` | Demo agent shows "High" confidence |
| `test_header_shows_target_info` | Target name, pack, timestamp displayed |
| `test_empty_failures_message` | All passed → "No failures!" message |

## Definition of Done

- [ ] Score badge renders with correct color/label for all ranges
- [ ] Category breakdown shows horizontal bars per category
- [ ] Top failures listed and sorted by severity
- [ ] [View Details] navigates to scenario detail
- [ ] Confidence badge displayed
- [ ] Page matches spec wireframe layout
- [ ] All tests pass
