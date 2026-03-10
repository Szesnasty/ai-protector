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
