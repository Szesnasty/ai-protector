# 01 — Target Configuration Form

> **Layer:** Frontend (Nuxt 3 + Vuetify 3)
> **Phase:** 2 (Custom Endpoints) — MVP
> **Depends on:** Phase 1 complete

## Scope

The target configuration form shared by Local Agent and Hosted Endpoint flows. Captures: endpoint URL, target name, auth, type, timeout, safe mode, environment.

## Implementation Steps

### Step 1: Create form component

- Reusable component: `RedTeamTargetForm.vue`
- Props: `targetType: "local_agent" | "hosted_endpoint"`
- Used from landing page after clicking Local Agent or Hosted Endpoint card

### Step 2: Required fields

- **Endpoint URL** (required) — text input with URL validation
  - Local Agent prefill: `http://localhost:`
  - Hosted Endpoint prefill: `https://`

### Step 3: Optional fields

- **Target name** — free text, shown in results/reports instead of raw URL
- **Auth header** — masked input (password-type), "Bearer sk-..." placeholder
- **Type** — radio: "Chatbot / API" (default) | "Tool-calling agent"
  - Affects pack recommendation on configure screen

### Step 4: Advanced section (collapsed by default)

- **Request timeout** — dropdown: 10s, 30s (default), 60s, 120s
- **Safe mode** — toggle: Off (Local default) / On (Hosted default)
  - Tooltip: "Skip scenarios that may trigger real actions (delete, transfer, etc.)"
- **Environment** (Hosted only) — radio: Staging | Internal | Production-like | Other

### Step 5: Safety notice (always visible)

- Warning card (not in Advanced — always shown):
  - "Benchmarks send realistic attack prompts. If your agent has real tools, use Safe mode or a staging environment."

### Step 6: [Test Connection] button

- Triggers connectivity check (see spec 02)
- Shown after URL is entered, before [Continue]

### Step 7: [Continue] button

- Enabled only after successful [Test Connection]
- Navigates to `/red-team/configure` with target config as state/query

### Step 8: Differences per target type

| | Local Agent | Hosted Endpoint |
|---|---|---|
| URL prefill | `http://localhost:` | `https://` |
| Auth | Hidden by default | Shown by default |
| Environment | Not shown | Shown |
| Safe mode default | Off | **On** |

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_form_renders_for_local` | Local Agent form with correct prefill |
| `test_form_renders_for_hosted` | Hosted form with auth + environment |
| `test_url_validation` | Invalid URL → error message |
| `test_safe_mode_defaults` | Local=Off, Hosted=On |
| `test_type_selection` | Chatbot/API vs Tool-calling radio works |
| `test_continue_disabled_without_test` | [Continue] greyed out before [Test Connection] |
| `test_continue_navigates` | After test → [Continue] → configure page |
| `test_safety_notice_visible` | Warning always shown, not in collapsed Advanced |
| `test_advanced_collapsed` | Advanced section collapsed by default |

## Definition of Done

- [ ] Form component works for both Local Agent and Hosted Endpoint
- [ ] All fields render and validate correctly
- [ ] [Test Connection] → [Continue] flow enforced
- [ ] Safe mode defaults correct per target type
- [ ] Safety notice always visible
- [ ] Form state passed to configure page
- [ ] All tests pass
