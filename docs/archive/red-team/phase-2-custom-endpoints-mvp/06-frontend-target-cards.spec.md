# 06 — Frontend Target Cards (Landing Page Update)

> **Layer:** Frontend (Nuxt 3 + Vuetify 3)
> **Phase:** 2 (Custom Endpoints) — MVP
> **Depends on:** Target form (Phase 2, step 01)

## Scope

Enable the Local Agent and Hosted Endpoint cards on the `/red-team` landing page. They were disabled/greyed in Phase 1.

## Implementation Steps

### Step 1: Activate Local Agent card

- Remove "Coming soon" badge
- Click → navigates to `/red-team/target?type=local_agent`
- Icon: `mdi-laptop`, button: [Configure]
- Description: "Agent running on localhost"

### Step 2: Activate Hosted Endpoint card

- Remove "Coming soon" badge
- Click → navigates to `/red-team/target?type=hosted_endpoint`
- Icon: `mdi-web`, button: [Configure]
- Description: "Staging, prod, or internal URL behind auth"

### Step 3: Create target form page

- Route: `/red-team/target`
- Query param: `type=local_agent | hosted_endpoint`
- Renders `RedTeamTargetForm.vue` (from Phase 2, step 01)
- On [Continue] → navigates to `/red-team/configure` with target config

### Step 4: Registered Agent card remains disabled

- Keep "Coming soon" / "Iteration 2+" badge
- Will be enabled in Phase 3

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_local_agent_card_active` | Card clickable, navigates to form |
| `test_hosted_endpoint_card_active` | Card clickable, navigates to form |
| `test_registered_agent_still_disabled` | Card disabled with badge |
| `test_target_form_page_renders` | Form page loads for both types |
| `test_continue_navigates_to_configure` | Form → [Continue] → configure page |

## Definition of Done

- [ ] Local Agent and Hosted Endpoint cards active and clickable
- [ ] Cards navigate to target configuration form
- [ ] Target form page renders correctly for both types
- [ ] Flow: card → form → test connection → continue → configure → run
- [ ] Registered Agent card remains disabled
- [ ] All tests pass
