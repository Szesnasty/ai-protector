# 03 — Frontend Configure (`/red-team/configure`)

> **Layer:** Frontend (Nuxt 3 + Vuetify 3)
> **Phase:** 1 (Demo Agent) — MVP
> **Depends on:** API Routes (Phase 1, step 01), Pack list endpoint

## Scope

Run configuration screen. In Phase 1, this is minimal: target is "Demo Agent" (pre-set), pack is "Core Security" (pre-selected), policy selector available.

## Implementation Steps

### Step 1: Create route and page component

- Route: `/red-team/configure`
- Read `target=demo` from query params
- Page: `app/pages/red-team/configure.vue`

### Step 2: Display target info

- "Target: Demo Agent (Balanced policy)" with [Change] link back to `/red-team`
- Target badge/chip showing what the user selected

### Step 3: Fetch and display attack packs

- Call `GET /v1/benchmark/packs`
- Render radio group:
  - **Core Security** ★ default — preselected, scenario count, description, evaluation method note
  - **Agent Threats** — available but secondary, with note "Recommended for tool-calling agents"
  - Advanced packs (Full Suite, JailbreakBench) — greyed out, "Iteration 3+"

### Step 4: Policy selector

- Dropdown with seed policies: Fast, Balanced (default), Strict, Paranoid
- For demo agent, policy is meaningful (changes the pipeline behavior)

### Step 5: [Run Benchmark] button

- POST to `/v1/benchmark/runs` with: `{ target_type: "demo", pack: "core_security", policy: "balanced" }`
- On success → navigate to `/red-team/run/{id}`
- Loading state on button during POST

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_page_renders_for_demo` | Configure page renders with demo target |
| `test_core_security_preselected` | Core Security pack is selected by default |
| `test_pack_list_fetched` | Packs loaded from API |
| `test_policy_selector_works` | Policy dropdown changes selection |
| `test_run_benchmark_creates_run` | Click → POST → navigate to run page |
| `test_loading_state_on_submit` | Button shows loading during API call |

## Definition of Done

- [ ] Configure page renders with pack selection and policy dropdown
- [ ] Core Security pre-selected for demo target
- [ ] [Run Benchmark] creates a run and navigates to progress page
- [ ] Page matches spec wireframe
- [ ] All tests pass
