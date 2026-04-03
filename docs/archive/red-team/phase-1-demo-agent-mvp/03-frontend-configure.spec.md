# 03 — Frontend Configure (`/red-team/configure`)

> **Layer:** Frontend (Nuxt 3 + Vuetify 3)
> **Phase:** 1 (Demo Agent) — MVP
> **Depends on:** API Routes (Phase 1, step 01), Pack list endpoint

## Scope

Run configuration screen. In Phase 1, this is minimal: target is "Demo Agent" (pre-set), pack is "Core Security" (pre-selected), policy auto-selected.

> **UX rule:** This screen is a **confirmation, not a form.** For Demo Agent, the user sees what will happen and clicks one button. No thinking required.

## Implementation Steps

### Step 1: Create route and page component

- Route: `/red-team/configure`
- Read `target=demo` from query params
- Page: `app/pages/red-team/configure.vue`

### Step 2: Display target info

- "Target: Demo Agent" with [Change] link back to `/red-team`
- Target badge/chip showing what the user selected

### Step 3: Fetch and display attack packs

- Call `GET /v1/benchmark/packs`
- Render radio group:
  - **Core Security** ★ recommended — preselected, scenario count, user-facing description:
    - "Tests prompt injection, jailbreak, data leaks, and harmful outputs."
    - "Works on any chatbot or API endpoint."
    - ⚠️ NO evaluation method details (no "regex", "keyword", "deterministic" — user doesn't care)
  - **Agent Threats** — available but secondary: "Tests tool abuse, role bypass, and privilege escalation. Best for tool-calling agents."
  - Advanced packs (Full Suite, JailbreakBench) — greyed out, "Coming soon"

### Step 4: [Run Benchmark] hero button

- **Primary action — above fold, above Advanced section**
- POST to `/v1/benchmark/runs` with: `{ target_type: "demo", pack: "core_security", policy: "balanced" }`
- On success → navigate to `/red-team/run/{id}`
- Loading state on button during POST

### Step 5: Advanced section (collapsed by default)

- Policy dropdown: Fast, Balanced (default), Strict, Paranoid
- For demo agent, policy is meaningful but most users skip this entirely
- This section is BELOW the Run button — user must scroll down to find it

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_page_renders_for_demo` | Configure page renders with demo target |
| `test_core_security_preselected` | Core Security pack is selected by default |
| `test_pack_list_fetched` | Packs loaded from API |
| `test_pack_descriptions_user_facing` | No technical jargon ("regex", "deterministic") in pack descriptions |
| `test_run_button_above_advanced` | Run button renders above Advanced section |
| `test_run_benchmark_creates_run` | Click → POST → navigate to run page |
| `test_loading_state_on_submit` | Button shows loading during API call |
| `test_advanced_collapsed` | Policy dropdown hidden in collapsed Advanced section |

## Definition of Done

- [ ] Configure page renders with pack selection
- [ ] Pack descriptions are user-facing (no "regex", "keyword", "deterministic")
- [ ] Core Security pre-selected for demo target
- [ ] [Run Benchmark] is the hero button, above Advanced section
- [ ] Policy dropdown in collapsed Advanced section
- [ ] [Run Benchmark] creates a run and navigates to progress page
- [ ] All tests pass
