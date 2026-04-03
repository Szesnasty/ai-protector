# 07 — CTA Protection Paths (Variant B)

> **Layer:** Frontend
> **Phase:** 2 (Custom Endpoints) — MVP
> **Depends on:** Results page (Phase 1)

## Scope

When the user runs a benchmark on an unprotected custom endpoint, the CTA section shows two protection paths: Quick (Proxy Setup) and Deep (Agent Wizard).

## Implementation Steps

### Step 1: Target type detection for CTA variant

- CTA Variant A (already built in Phase 1) → demo agent / registered agent
- CTA Variant B → local agent / hosted endpoint (unprotected targets)
- Results page checks `target_type` and renders the appropriate variant

### Step 2: CTA Variant B layout

- "Protect this endpoint"
- "Your agent has {N} critical security gaps."
- Two path cards:
  - **Quick — Proxy Setup**: "Route traffic through AI Protector. No code changes." → [Set up Proxy →]
  - **Deep — Agent Wizard**: "Register tools, roles, RBAC. Most precise protection." → [Open Wizard →]
- Plus: [Re-run Benchmark] and [Export Report] buttons

### Step 3: [Set up Proxy] link

- Navigate to proxy setup page (or instructions page)
- Pass context: endpoint URL from the benchmark run
- Instructions: "Change your agent's base URL from {original_url} to {protector_proxy_url}"

### Step 4: [Open Wizard] link

- Navigate to Agent Wizard: `/agents/new`
- Pre-fill data from the target config: URL, name, type
- After wizard completion → user returns to Red Team, can re-run as Registered Agent (Phase 3)

### Step 5: [Re-run Benchmark] button

- Same flow as Phase 1 re-run but for custom endpoint
- If proxy was set up → re-run goes through the pipeline → score improves

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_cta_variant_b_for_local` | Local agent → CTA Variant B shown |
| `test_cta_variant_b_for_hosted` | Hosted endpoint → CTA Variant B shown |
| `test_cta_variant_a_for_demo` | Demo agent → CTA Variant A (unchanged) |
| `test_proxy_link_navigates` | [Set up Proxy] → proxy setup page |
| `test_wizard_link_prefills` | [Open Wizard] → wizard with pre-filled URL |
| `test_rerun_for_custom` | Re-run creates new benchmark for same endpoint |

## Definition of Done

- [ ] CTA Variant B renders for unprotected targets
- [ ] Both protection paths (Proxy, Wizard) link to correct destinations
- [ ] Context (URL, name) passed to proxy/wizard pages
- [ ] Re-run works for custom endpoints
- [ ] CTA variant selection based on target_type
- [ ] All tests pass
