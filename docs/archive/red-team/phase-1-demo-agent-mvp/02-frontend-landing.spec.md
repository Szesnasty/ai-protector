# 02 — Frontend Landing (`/red-team`)

> **Layer:** Frontend (Nuxt 3 + Vuetify 3)
> **Phase:** 1 (Demo Agent) — MVP
> **Depends on:** API Routes (Phase 1, step 01)

## Scope

The `/red-team` entry point page. In Phase 1, only the **Demo Agent** card is active. Other cards (Local Agent, Hosted Endpoint, Registered Agent) are shown but disabled/greyed out with "Coming soon" labels.

## Implementation Steps

### Step 1: Create route and page component

- Route: `/red-team`
- Page: `app/pages/red-team/index.vue`
- Page title: "Red Team — Security Tests"
- Subtitle: "Test your AI endpoint in minutes."

### Step 2: Implement target cards grid

- 4 cards in a 2×2 grid (responsive)
- **Demo Agent** — active, clickable, icon `mdi-robot`, button [Start]
- **Local Agent** — disabled, icon `mdi-laptop`, "Coming soon" badge
- **Hosted Endpoint** — disabled, icon `mdi-web`, "Coming soon" badge
- **Registered Agent** — disabled, icon `mdi-shield-check`, "Coming soon" badge

### Step 3: Sidebar navigation update

- Add "Test" group above "Create" in sidebar
- Red Team entry with icon `mdi-shield-search` or `mdi-target`
- Route: `/red-team`
- Highlight as active when on any `/red-team/*` route

### Step 4: Demo Agent click behavior

- Click "Demo Agent" → [Start] → navigate to `/red-team/configure?target=demo`
- No form, no input — zero-config path

### Step 5: Empty state for Recent Runs (placeholder)

- Section below target cards: "Recent Runs" (empty message: "No benchmark runs yet. Start one above!")
- This will be populated in Phase 3, but the section structure should exist

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_page_renders` | `/red-team` renders without errors |
| `test_demo_agent_card_active` | Demo Agent card is clickable |
| `test_other_cards_disabled` | Local Agent, Hosted, Registered are disabled |
| `test_demo_click_navigates` | Clicking Demo Agent → navigates to `/red-team/configure?target=demo` |
| `test_sidebar_has_red_team` | Sidebar shows "Red Team" under "Test" group |
| `test_recent_runs_empty_state` | Empty runs shows placeholder text |

## Definition of Done

- [ ] `/red-team` page renders with 4 target cards
- [ ] Demo Agent card navigates to configure page
- [ ] Other cards disabled with "Coming soon"
- [ ] Sidebar updated with Red Team entry
- [ ] Page matches the spec wireframe layout
- [ ] All tests pass
