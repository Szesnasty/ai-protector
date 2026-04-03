# 05 — Registered Agent Target

> **Layer:** Full-stack
> **Phase:** 3 (Proof & Conversion)
> **Depends on:** Agent Wizard (existing), MVP complete

## Scope

Enable the "Registered Agent" card on the landing page. Users select an agent registered via the Agent Wizard and run benchmarks with full tool/role metadata.

## Implementation Steps

### Step 1: Enable registered agent card

- Remove "Coming soon" badge
- Click → dropdown of registered agents from Agent Wizard
- [Select Agent] → configure page with agent context

### Step 2: Backend agent lookup

- `GET /v1/agents` → list registered agents with tools, roles, RBAC
- Pass `agent_id` in target_config

### Step 3: Enhanced evaluation

- Registered agents have full pipeline trace → `confidence: "high"`
- Tool metadata available → richer tool_call_detect evaluation
- RBAC rules available → access control scenarios more precise

### Step 4: Agent Threats pack activation

- For registered agents with tools → Agent Threats pack auto-recommended
- Full Agent Threats scenarios (not just stub)

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_registered_agent_card_active` | Card clickable |
| `test_agent_dropdown_populates` | Registered agents shown |
| `test_high_confidence_for_registered` | Confidence = high |
| `test_agent_threats_recommended` | Pack auto-selected for tool-calling agents |

## Definition of Done

- [ ] Registered Agent card active with agent selection
- [ ] Full pipeline trace for registered agents
- [ ] Agent Threats pack working for tool-calling agents
- [ ] All tests pass
