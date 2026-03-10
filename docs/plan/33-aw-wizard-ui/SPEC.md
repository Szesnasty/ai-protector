# Step 33 — Agent Wizard UI

**Prereqs:** Steps 26–32 (all backend APIs)
**Spec ref:** agents-v1.spec.md → all Reqs (frontend counterpart)
**Effort:** 4–5 days
**Output:** Full wizard flow in Nuxt frontend — register, configure, validate, deploy

---

## Why this step matters

Backend APIs are useless without a UI. The wizard is the ENTIRE user-facing
product for agent onboarding. User journey:

```
sidebar "Agents" → agents list → "+ New Agent" → wizard (7 steps) → agent detail
```

Current sidebar has:
- Playground, Compare, Agent Demo, Agent Traces, Security Rules
- Manage: Policies, Request Log, Analytics, Settings

New sidebar structure:
- **Agents** (new top-level item, before Playground)
- Playground, Compare, Agent Traces, Security Rules
- Manage: Policies, Request Log, Analytics, Settings
- Agent Demo moves to a link inside an agent's detail page (or stays for backward compat)

---

## Sub-steps

### 33a — Sidebar + routing

Add "Agents" nav item and new page routes:

```typescript
// in app-nav-drawer.vue navItems (insert at position 0)
{ title: 'Agents', icon: 'mdi-robot-outline', to: '/agents' }
```

New pages:
- `/agents` — agents list
- `/agents/new` — wizard (new agent)
- `/agents/:id` — agent detail (tabbed view)
- `/agents/:id/edit` — edit wizard (pre-filled)

**DoD:**
- [ ] "Agents" in sidebar, highlighted when on /agents/*
- [ ] All 4 routes resolve to correct pages (placeholder content OK)
- [ ] Breadcrumbs: Agents > [name] > [tab]
- [ ] Tests: navigation renders, routes resolve

### 33b — Agents list page

`/agents` — table/card list of registered agents.

| Column | Source |
|--------|--------|
| Name | agent.name |
| Risk level | agent.risk_classification (chip: low/medium/high/critical) |
| Rollout mode | agent.rollout_mode (chip: observe/warn/enforce) |
| Tools | count of registered tools |
| Last validation | score badge (12/12 ✓) or "Not run" |
| Created | relative time |

Actions:
- "+ New Agent" button → `/agents/new`
- Row click → `/agents/:id`
- Search/filter by name, risk, rollout mode

Empty state: illustration + "Register your first agent" CTA.

**DoD:**
- [ ] Table renders agents from `GET /agents`
- [ ] Risk + rollout chips with correct colors
- [ ] "+ New Agent" button navigates to wizard
- [ ] Empty state when no agents exist
- [ ] Tests: renders list, empty state, click navigates

### 33c — Wizard shell (stepper component)

Reusable vertical stepper for the 7-step wizard:

```
Step 1: Describe Agent        ✓ completed
Step 2: Register Tools        ● current
Step 3: Define Roles          ○ upcoming
Step 4: Configure Security    ○
Step 5: Generate Kit          ○
Step 6: Validate              ○
Step 7: Deploy                ○
```

Features:
- `v-stepper` (Vuetify) with vertical layout
- Each step validates before allowing next
- Back button always available
- Progress persisted in browser (localStorage) — resume if user leaves
- Step content loaded as named slot

**DoD:**
- [ ] `AgentWizardStepper` component with 7 steps
- [ ] Step validation: cannot advance without completing current
- [ ] Back button on all steps except first
- [ ] State persisted to localStorage, restored on mount
- [ ] Tests: stepper renders, advance/back works, validation blocks

### 33d — Step 1: Describe Agent

Form fields:
- **Name** (required, unique, validated against API)
- **Description** (required, textarea, what the agent does)
- **Framework** (select: LangGraph / CrewAI / raw Python / proxy-only)
- **Risk classification** (read-only, computed after tool registration — shows "TBD")

Calls: `POST /agents` on "Next" → creates agent, gets ID for subsequent steps.

**DoD:**
- [ ] Form with validation (name required, min 3 chars)
- [ ] Framework select with icons
- [ ] "Next" creates agent via API, stores ID in wizard state
- [ ] Error handling: duplicate name, API errors
- [ ] Tests: form renders, validation works, API called on submit

### 33e — Step 2: Register Tools

Interactive tool registration:
- "+ Add Tool" button opens dialog
- Each tool: name, description, sensitivity level, arguments (name + type + description)
- Visual list of added tools with edit/delete
- Import from JSON/YAML option (paste or upload)

Calls: `POST /agents/:id/tools` for each tool.

**DoD:**
- [ ] Add/edit/delete tools in the wizard
- [ ] Tool form: name, description, sensitivity (low/medium/high/critical), args
- [ ] Import from JSON/YAML (validates schema)
- [ ] Tools saved via API as they're added
- [ ] Tests: add tool, edit tool, delete tool, import works

### 33f — Step 3: Define Roles

Role management:
- "+ Add Role" button
- Each role: name, allowed tools (multi-select from step 2 tools)
- Visual permission matrix: roles × tools grid with checkboxes
- Pre-fill suggestion based on risk classification

Calls: `POST /agents/:id/roles` for each role.

**DoD:**
- [ ] Add/edit/delete roles
- [ ] Permission matrix: interactive grid of roles × tools
- [ ] At least one role required to proceed
- [ ] Roles saved via API
- [ ] Tests: add role, assign tools, matrix renders correctly

### 33g — Step 4: Configure Security

Security config selection:
- **Policy pack** selection (cards with description):
  - Strict (recommended for high-risk)
  - Standard (recommended default)
  - Permissive (for low-risk internal agents)
  - Custom (advanced — edit individual policies)
- **Limits** preview/edit:
  - Rate limit (requests/min)
  - Token budget (per session)
  - Cost budget (per day)
- **Preview generated config** — read-only YAML viewer

Calls: `POST /agents/:id/config/generate` with selected pack + overrides.

**DoD:**
- [ ] Policy pack cards with selection
- [ ] Limits form with sensible defaults per risk level
- [ ] Generated config preview (syntax-highlighted YAML)
- [ ] Config regenerates when pack/limits change
- [ ] Tests: select pack, modify limits, preview updates

### 33h — Step 5: Generate Integration Kit

Kit generation + download:
- "Generate Kit" button
- Preview of generated files (tabbed code viewer):
  - `rbac.yaml`
  - `limits.yaml`
  - `policy.yaml`
  - Framework wrapper (e.g., `protector_middleware.py`)
  - `test_security.py`
  - `.env.protector`
  - `README.md`
- "Download ZIP" button
- "Copy to clipboard" per file

Calls: `POST /agents/:id/kit/generate` → renders preview.
       `GET /agents/:id/kit/download` → ZIP file.

**DoD:**
- [ ] Generate button calls API
- [ ] Tabbed preview of all generated files
- [ ] Syntax highlighting (Python, YAML, Markdown)
- [ ] Download ZIP button
- [ ] Copy-to-clipboard per file
- [ ] Tests: generate renders files, download triggers, copy works

### 33i — Step 6: Validate

Run validation and show results:
- "Run Validation" button
- Progress indicator during run
- Results scorecard:
  - Overall score: 12/12 ✓ (green) or 10/12 ✗ (red)
  - Category breakdown with pass/fail per test
  - Failed test detail with recommendation
- "Re-run" after fixing config

Calls: `POST /agents/:id/validate` → shows results.

**DoD:**
- [ ] Run button triggers validation API
- [ ] Loading state during validation
- [ ] Scorecard with category breakdown
- [ ] Failed tests show recommendations
- [ ] Re-run button after changes
- [ ] Tests: renders results, shows failures correctly

### 33j — Step 7: Deploy (Rollout)

Rollout mode selection + activation:
- Current mode indicator (defaults to OBSERVE)
- Explanation of each mode (observe/warn/enforce) with visual
- "Activate in observe mode" button (primary CTA)
- Info: "You can promote to warn/enforce later from the agent detail page"
- Confetti / success animation on completion 🎉

Calls: `PATCH /agents/:id/rollout` with `{ mode: "observe" }`.

**DoD:**
- [ ] Mode explanation cards
- [ ] Activate button sets rollout mode
- [ ] Success state with next steps info
- [ ] Link to agent detail page
- [ ] Tests: activate calls API, shows success

### 33k — Agent detail page

`/agents/:id` — tabbed view of a registered agent:

| Tab | Content |
|-----|---------|
| Overview | Agent info, risk level, rollout mode, created date |
| Tools | Tool list with sensitivity levels |
| Roles | Roles + permission matrix (read-only or editable) |
| Config | Generated YAML configs (viewable, re-generate button) |
| Integration Kit | Generated files + download |
| Validation | Latest results + re-run + history |
| Traces | Agent-specific traces (from step 32 API) |
| Incidents | Agent-specific incidents (from step 32 API) |

Rollout promotion controls:
- Current mode badge
- "Promote to warn" / "Promote to enforce" button
- Readiness check display (from 31e API)
- Demotion buttons (warn → observe, enforce → warn)

**DoD:**
- [ ] Tabbed layout with all 8 tabs
- [ ] Each tab loads data from corresponding API
- [ ] Rollout promotion/demotion controls
- [ ] Readiness check displayed before promotion
- [ ] Tests: tabs render, data loads, promotion works

### 33l — Composables + API client

Shared composables for agent operations:

```typescript
// composables/useAgents.ts
useAgents()      // list + CRUD
useAgentTools()  // tools for specific agent
useAgentRoles()  // roles for specific agent
useAgentConfig() // config generation
useAgentKit()    // kit generation + download
useAgentValidation()  // validation runs
useAgentRollout()     // rollout mode management
useAgentTraces()      // traces + incidents
```

Each composable:
- Reactive state (data, loading, error)
- CRUD methods
- Auto-refresh where appropriate

**DoD:**
- [ ] All composables implemented with TypeScript types
- [ ] Error handling + loading states
- [ ] Consistent pattern with existing composables (usePlaygroundChat, etc.)
- [ ] Types match API schemas exactly
- [ ] Tests: composables return correct data shapes

---

## Sequence

Build order within step 33:

1. **33l** (composables) — API layer first, everything depends on it
2. **33a** (sidebar + routing) — navigation scaffolding
3. **33b** (agents list) — first visible page
4. **33c** (wizard shell) — stepper component
5. **33d → 33j** (wizard steps 1–7) — sequential, each builds on previous
6. **33k** (agent detail) — needs all APIs working

Total: ~12 components + 8 composables + 4 pages

---

## Test plan

Minimum **72 tests** across 12 sub-steps.
Unit tests in `tests/components/` (Vitest + Vue Test Utils).
E2E tests in `tests/e2e/` (Playwright or Cypress).

### 33a tests — Sidebar + routing (6 tests)

| # | Test | Assert |
|---|------|--------|
| 1 | `test_sidebar_has_agents_item` | "Agents" nav item rendered with mdi-robot-outline icon |
| 2 | `test_agents_item_is_first` | "Agents" is first item in nav list |
| 3 | `test_route_agents_list` | /agents resolves, renders page |
| 4 | `test_route_agents_new` | /agents/new resolves, renders wizard |
| 5 | `test_route_agents_detail` | /agents/:id resolves, renders detail |
| 6 | `test_sidebar_active_state` | Navigating to /agents/xxx highlights "Agents" in sidebar |

### 33b tests — Agents list page (8 tests)

| # | Test | Assert |
|---|------|--------|
| 7 | `test_list_renders_agents` | Mock 3 agents → 3 rows rendered |
| 8 | `test_list_risk_chip_colors` | LOW=green, MEDIUM=amber, HIGH=orange, CRITICAL=red |
| 9 | `test_list_rollout_chip` | observe=blue, warn=amber, enforce=green |
| 10 | `test_list_tool_count` | Tools column shows correct count |
| 11 | `test_list_new_agent_button` | "+ New Agent" button exists, navigates to /agents/new |
| 12 | `test_list_empty_state` | 0 agents → "Register your first agent" CTA |
| 13 | `test_list_row_click_navigates` | Click row → navigates to /agents/:id |
| 14 | `test_list_search_filter` | Type in search → list filtered by name |

### 33c tests — Wizard stepper (8 tests)

| # | Test | Assert |
|---|------|--------|
| 15 | `test_stepper_renders_7_steps` | 7 step headers visible |
| 16 | `test_stepper_starts_at_step_1` | Step 1 active on mount |
| 17 | `test_stepper_next_disabled_without_validation` | "Next" disabled when step not valid |
| 18 | `test_stepper_next_advances` | Complete step 1 → click Next → step 2 active |
| 19 | `test_stepper_back_works` | Click Back on step 2 → step 1 active |
| 20 | `test_stepper_no_back_on_step_1` | Step 1 has no Back button |
| 21 | `test_stepper_persists_to_localStorage` | Advance to step 3 → localStorage has wizard state |
| 22 | `test_stepper_restores_from_localStorage` | Set localStorage wizard state → mount → resumes at step 3 |

### 33d tests — Step 1: Describe Agent (6 tests)

| # | Test | Assert |
|---|------|--------|
| 23 | `test_describe_form_renders` | Name, description, framework fields visible |
| 24 | `test_describe_name_required` | Submit empty name → validation error shown |
| 25 | `test_describe_name_min_3` | Submit "ab" → validation error |
| 26 | `test_describe_framework_select` | 4 options: LangGraph, CrewAI, raw Python, proxy-only |
| 27 | `test_describe_next_calls_api` | Fill form + Next → POST /agents called |
| 28 | `test_describe_duplicate_name_error` | API returns 409 → "Name already taken" shown |

### 33e tests — Step 2: Register Tools (8 tests)

| # | Test | Assert |
|---|------|--------|
| 29 | `test_tools_empty_state` | Initially shows "No tools added" + "Add Tool" button |
| 30 | `test_tools_add_dialog` | Click "+ Add Tool" → dialog opens with form |
| 31 | `test_tools_add_saves_to_api` | Fill tool form + Save → POST /agents/:id/tools called |
| 32 | `test_tools_appears_in_list` | After add, tool appears in visual list |
| 33 | `test_tools_edit` | Click edit → dialog pre-filled, save calls PATCH |
| 34 | `test_tools_delete` | Click delete → confirm dialog → DELETE called |
| 35 | `test_tools_import_json` | Paste valid JSON → tools added |
| 36 | `test_tools_import_invalid` | Paste invalid JSON → error shown |

### 33f tests — Step 3: Define Roles (6 tests)

| # | Test | Assert |
|---|------|--------|
| 37 | `test_roles_add` | "+ Add Role" → dialog, save calls API |
| 38 | `test_roles_permission_matrix_renders` | Grid shows roles × tools |
| 39 | `test_roles_matrix_checkbox_toggle` | Click checkbox → permission toggled, API called |
| 40 | `test_roles_at_least_one_required` | 0 roles → "Next" disabled |
| 41 | `test_roles_delete` | Delete role → removed from matrix |
| 42 | `test_roles_inheritance_select` | Role form has "Inherits from" dropdown |

### 33g tests — Step 4: Configure Security (6 tests)

| # | Test | Assert |
|---|------|--------|
| 43 | `test_security_pack_cards` | 5 policy pack cards rendered |
| 44 | `test_security_pack_selection` | Click card → selected state, pack value set |
| 45 | `test_security_limits_form` | Rate limit, token budget, cost budget inputs visible |
| 46 | `test_security_limits_defaults` | Defaults populated per risk level |
| 47 | `test_security_config_preview` | YAML preview shown, syntax highlighted |
| 48 | `test_security_preview_updates` | Change pack → preview YAML updates |

### 33h tests — Step 5: Generate Kit (6 tests)

| # | Test | Assert |
|---|------|--------|
| 49 | `test_kit_generate_button` | "Generate Kit" button calls POST /agents/:id/integration-kit |
| 50 | `test_kit_tabbed_preview` | After generate, 7 tabs shown (one per file) |
| 51 | `test_kit_syntax_highlighting` | Python files have syntax classes, YAML files have syntax classes |
| 52 | `test_kit_download_button` | "Download ZIP" button triggers GET download |
| 53 | `test_kit_copy_button` | "Copy" button on each tab copies file content |
| 54 | `test_kit_loading_state` | During generation, loading indicator shown |

### 33i tests — Step 6: Validate (6 tests)

| # | Test | Assert |
|---|------|--------|
| 55 | `test_validate_run_button` | "Run Validation" calls POST /agents/:id/validate |
| 56 | `test_validate_loading` | During run, progress indicator shown |
| 57 | `test_validate_scorecard_pass` | 12/12 → green badge, all categories green |
| 58 | `test_validate_scorecard_fail` | 10/12 → red badge, failed tests listed |
| 59 | `test_validate_failed_recommendation` | Failed test shows recommendation text |
| 60 | `test_validate_rerun_button` | After results, "Re-run" button visible |

### 33j tests — Step 7: Deploy (4 tests)

| # | Test | Assert |
|---|------|--------|
| 61 | `test_deploy_mode_cards` | 3 mode explanation cards rendered |
| 62 | `test_deploy_activate_button` | "Activate" calls PATCH /agents/:id/rollout |
| 63 | `test_deploy_success_state` | After activation, success message + link to detail page |
| 64 | `test_deploy_next_steps` | Success view shows "promote to warn/enforce later" info |

### 33k tests — Agent detail page (8 tests)

| # | Test | Assert |
|---|------|--------|
| 65 | `test_detail_has_8_tabs` | 8 tab headers rendered |
| 66 | `test_detail_overview_tab` | Overview shows agent info, risk, rollout mode |
| 67 | `test_detail_tools_tab` | Tools tab lists agent's tools |
| 68 | `test_detail_config_tab` | Config tab shows YAML with re-generate button |
| 69 | `test_detail_validation_tab` | Validation tab shows latest results + history |
| 70 | `test_detail_traces_tab` | Traces tab shows filtered trace list |
| 71 | `test_detail_rollout_promote_button` | "Promote to warn" button visible in observe mode |
| 72 | `test_detail_rollout_readiness` | Readiness check info displayed before promotion |

### 33l tests — Composables (8 tests)

| # | Test | Assert |
|---|------|--------|
| 73 | `test_useAgents_list` | useAgents().agents returns reactive agent list |
| 74 | `test_useAgents_create` | useAgents().create() calls POST /agents |
| 75 | `test_useAgentTools_crud` | useAgentTools(id).create/update/delete call correct endpoints |
| 76 | `test_useAgentRoles_crud` | useAgentRoles(id).create/update/delete call correct endpoints |
| 77 | `test_useAgentConfig_generate` | useAgentConfig(id).generate() calls POST generate-config |
| 78 | `test_useAgentKit_download` | useAgentKit(id).download() triggers file download |
| 79 | `test_useAgentValidation_run` | useAgentValidation(id).run() calls POST validate |
| 80 | `test_composable_error_handling` | API error → composable.error is set, loading=false |
