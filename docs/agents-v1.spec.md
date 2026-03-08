# AI Protector — Agents v1 Specification

> **Scope:** Agents as a standalone product pillar — registration, protection, validation, rollout, observability
> **Prerequisite:** MVP (proxy firewall, playground, agent demo) — done
> **Minimum product truth:** "AI Protector helps you register an agent, define tool permissions, generate deterministic guardrails, validate them with attack tests, and roll them out with visibility."

---

## Product pillar: Agents

Agents is a **separate section** in AI Protector — not scattered across Policies, Demo, or Analytics.

Everything that answers "how do I secure this specific agent?" lives here.

### Sidebar layout (v1)

```
Dashboard
Playground
Compare
Policies             ← global policy library
Agents               ← NEW: onboarding + lifecycle
Traces               ← renamed from "Agent Traces"
Analytics
Settings
```

### Inside Agents

```
Agents List          ← entry point, all registered agents
New Agent Wizard     ← 7-step onboarding flow
Agent Detail         ← per-agent management
  Overview           ← profile, risk, active pack, incidents
  Tools & Access     ← tools table, roles, RBAC, confirmations, budgets
  Integration        ← generated config, code snippets, env vars, download
  Validation         ← attack packs, runs, scorecard
  Traces             ← blocked calls, redactions, confirmations, timings
  Rollout            ← observe / warn / enforce, envs, promotion
```

### What moves where

| Current location | New location | What changes |
|-----------------|-------------|--------------|
| Agent Demo (`/agent`) | Agents → Demo Agent | Becomes a reference/showcase agent, not the main entry point |
| Agent Traces (`/agent-traces`) | Agents → `{agent}` → Traces (and global Traces) | Per-agent traces inside agent detail, global view stays |
| Policies (`/policies`) | Policies (stays) | Global policy library; agent-specific binding happens in Agents |
| Security Rules (`/rules`) | Policies sub-section or stays | No change needed for v1 |

---

## The 7 v1 requirements

### Req 1: Agent registration

User must be able to say: what agent, has tools?, write actions?, touches PII?, risk level.

#### Current state

| Aspect | Status |
|--------|--------|
| Working code | **None** — no registration endpoint, no DB model |
| UI | **None** — no registration form |
| Reference | Agent demo has hardcoded `config.py` — not a registration flow |
| Documentation | `docs/agents-implementation/01-describe-agent.md` — full questionnaire spec |

#### Definition of Done

- [ ] **API:** `POST /agents` creates an agent profile
- [ ] **API:** `GET /agents` lists all registered agents
- [ ] **API:** `GET /agents/:id` returns agent detail
- [ ] **API:** `PATCH /agents/:id` updates agent profile
- [ ] **DB model:** `Agent` table — name, description, team, framework, has_tools, has_write_actions, touches_pii, risk_level (low/medium/high/critical), created_at, updated_at
- [ ] **Risk classification:** Auto-computed from capabilities (write + PII + public-facing → critical)
- [ ] **UI — Agents List:** Table with columns: name, team, environment, protection level, pack, last validation, rollout mode, status
- [ ] **UI — Register form:** Step 1 of wizard — name, description, framework, capabilities checkboxes, risk computed live
- [ ] **Test:** Create agent via API → appears in list → detail page accessible

---

### Req 2: Tools + roles registration

User must be able to: add tools, mark read/write/sensitive, assign roles, set default-deny, mark tools requiring confirmation.

#### Current state

| Aspect | Status |
|--------|--------|
| Working code | **Full** — `rbac_config.yaml`, `rbac/service.py`, `rbac/models.py`, `tools/registry.py` |
| Default-deny | **Working** — `check_permission()` returns DENY if `(role, tool)` not found |
| Confirmation flow | **Working** — `requires_confirmation` in RBAC config, pre-tool gate checks it |
| UI | **None** — no CRUD for tools or roles |
| Limitation | YAML-only, requires restart to change |

#### Definition of Done

- [ ] **API:** `POST /agents/:id/tools` registers a tool (name, description, category, sensitivity, requires_confirmation, arg_schema)
- [ ] **API:** `GET /agents/:id/tools` lists tools for an agent
- [ ] **API:** `POST /agents/:id/roles` creates a role with tool permissions
- [ ] **API:** `GET /agents/:id/roles` lists roles with permission matrix
- [ ] **DB model:** `AgentTool` table — agent_id, name, description, category (read/write/admin), sensitivity (low/medium/high/critical), requires_confirmation, arg_schema (JSON)
- [ ] **DB model:** `AgentRole` table — agent_id, name, inherits_from
- [ ] **DB model:** `RoleToolPermission` table — role_id, tool_id, scopes (JSON: [read, write]), sensitivity_override, requires_confirmation, conditions (JSON, nullable). Relational join table, not a flat JSON array — this needs to support scopes, confirmation, conditions, and per-role sensitivity overrides without schema migration later.
- [ ] **Default-deny:** If tool not in role's permission set → DENY (already works in code, must persist to DB)
- [ ] **UI — Tools & Access tab:** Tools table with inline edit, roles table, permission matrix grid (role × tool)
- [ ] **UI — Wizard step 2-3:** Tool registration form + role mapping
- [ ] **Hot reload:** RBAC config changes apply without restart (watch file or poll DB)
- [ ] **Test:** Register tool via API → assign to role → check_permission returns ALLOW; unassigned → DENY

---

### Req 3: Generated RBAC + policy config

After configuration, user must get a real artifact: rbac.yaml, limits config, basic policy pack.

#### Current state

| Aspect | Status |
|--------|--------|
| rbac.yaml | **Exists** — `rbac_config.yaml` in agent-demo, loaded at startup |
| Limits config | **Exists** — `limits/config.py` dataclass with per-role overrides |
| Policy packs | **Documented** — 5 packs in `04-policy-packs.md`, not as code templates |
| Generation | **None** — no auto-generation from agent profile |
| Policy CRUD | **Working** — proxy service has full policy API |

#### Definition of Done

- [ ] **Generation endpoint:** `POST /agents/:id/generate-config` → creates rbac.yaml + limits.yaml + policy pack based on agent profile + registered tools + roles
- [ ] **rbac.yaml output:** Valid YAML with roles, tool permissions, sensitivity, inheritance
- [ ] **limits.yaml output:** Valid YAML with per-role rate limits, token budgets, cost caps
- [ ] **Policy pack selection:** 5 pre-built packs (customer_support, internal_copilot, finance, hr, research) selectable in wizard
- [ ] **Policy pack = concrete template:** Each pack is a YAML file containing: (a) scanner toggles (pii_redaction, secrets_scanning, injection_detection — on/off), (b) threshold values (injection_score, risk_score, max_output_size), (c) limit defaults per role tier (rate, tokens, cost), (d) redaction mode (mask/replace/block), (e) confirmation rules (which sensitivity levels require it). Not just a name — a full config that produces deterministic runtime behavior.
- [ ] **Policy pack binding:** Selected pack is stored on agent record and loaded at runtime
- [ ] **Download:** User can download generated files as individual files or .zip
- [ ] **Copy-to-clipboard:** Each generated file has a copy button
- [ ] **UI — Wizard step 4:** Policy pack selector with comparison table
- [ ] **UI — Integration tab:** Shows generated configs with copy/download
- [ ] **Test:** Register agent with 3 tools + 2 roles → generate config → YAML is valid and contains all tools/roles → download works

---

### Req 4: Working integration kit

Generated code that user copies into their project. This is the most important v1 deliverable.

> **⚠️ HIGHEST RISK:** This is the heart of the product and the hardest part of v1. The integration kit generator is not a "medium task" — it IS the main product. Scope guard for v1: generate only (1) LangGraph wrapper, (2) raw Python wrapper, (3) proxy-only mode, (4) config download, (5) smoke tests. Do not attempt advanced templating, multi-framework magic, or perfect code generation. Ship working files, iterate later.

#### Current state

| Aspect | Status |
|--------|--------|
| Pre-tool gate | **Full** — `pre_tool_gate.py` (463 lines), 5 checks: RBAC, args, context risk, limits, confirmation |
| Post-tool gate | **Full** — `post_tool_gate.py` (436 lines), 4 scans: PII, secrets, injection, size |
| Arg validation | **Full** — `validation/validator.py` + Pydantic schemas + injection patterns |
| Tests | **Full** — comprehensive test suite for all gates |
| Kit generator | **None** — working code exists but no packaging/templating |
| Framework support | LangGraph only — no CrewAI/AutoGen/raw Python wrappers |

#### Definition of Done

- [ ] **Generation endpoint:** `POST /agents/:id/integration-kit` → returns generated code files
- [ ] **Pre-tool gate snippet:** Python function parameterized with agent's RBAC + limits config
- [ ] **Post-tool gate snippet:** Python function parameterized with agent's policy pack settings (PII on/off, secrets on/off, etc.)
- [ ] **Arg validation schemas:** Pydantic models generated from registered tool schemas
- [ ] **Framework integration — LangGraph:** Graph node wrappers (`add_protection(graph)`)
- [ ] **Framework integration — raw Python:** `protected_tool_call()` wrapper function
- [ ] **Framework integration — proxy-only:** One-line base_url change
- [ ] **Env vars:** `.env.protector` with all required variables
- [ ] **Test file:** `test_security.py` with 4 smoke tests (RBAC block, injection block, PII redact, confirmation trigger)
- [ ] **Download all:** .zip with all files, README with integration instructions
- [ ] **UI — Wizard step 5:** Integration kit preview with per-file copy/download
- [ ] **UI — Integration tab:** Same content, accessible after wizard
- [ ] **Test:** Generate kit → extract → run `pytest test_security.py` → 4 tests pass

---

### Req 5: At least one real attack validation flow

User must see after integration: unauthorized → BLOCK, PII → REDACT, injection → BLOCK, over-budget → BLOCK/WARN.

#### Current state

| Aspect | Status |
|--------|--------|
| Unauthorized → BLOCK | **Working** — `_check_rbac()` in pre_tool_gate |
| PII → REDACT | **Working** — `scan_pii()` in post_tool_gate |
| Injection → BLOCK | **Working** — `_check_args()` + `scan_injection()` |
| Over-budget → BLOCK | **Working** — `_check_limits()` in pre_tool_gate (always BLOCK, no WARN) |
| Attack scenarios | **Working** — `scenarios.py` serves catalogue, `attack-scenarios-panel.vue` shows them |
| Automated validation runner | **None** — all scenarios are manual (user clicks and sends) |

#### Definition of Done

- [ ] **Validation runner:** `POST /agents/:id/validate` runs automated attack suite against agent's config
- [ ] **Test pack:** At least "basic" pack with 12 tests covering all 4 categories:
  - 3× RBAC: unauthorized tool call → BLOCKED
  - 3× injection: prompt injection in args → BLOCKED
  - 3× PII/secrets: sensitive data in output → REDACTED
  - 3× limits: over-budget/rate-limit → BLOCKED or WARNED
- [ ] **Results API:** Returns per-test: name, category, expected, actual, passed/failed, recommendation
- [ ] **Score:** Percentage pass rate (e.g., 11/12 = 92%)
- [ ] **Fix recommendations:** Failed tests include actionable fix suggestions
- [ ] **UI — Wizard step 6:** Run validation after integration, see results inline
- [ ] **UI — Validation tab:** Full validation history, re-run button, scorecard
- [ ] **Over-budget WARN:** Limits check returns WARN (not just BLOCK) when budget is close to exhaustion
- [ ] **Source of truth:** Validation tests run against the **generated config + AI Protector runtime** (gates, RBAC service, limits service), NOT against the user's live agent. This means: tests prove that the policy model works correctly. They do NOT prove that the user integrated it correctly. The UI must clearly state: "These tests validate your AI Protector configuration. To verify end-to-end integration, use the smoke tests in your integration kit." This distinction prevents users from thinking "I tested my agent" when they only tested the policy model.
- [ ] **Test:** Register agent with demo config → run validation → all 12 basic tests pass

---

### Req 6: Observe / Warn / Enforce rollout modes

Nobody wants hard blocks on day one. Progressive rollout is critical for adoption.

#### Current state

| Aspect | Status |
|--------|--------|
| Working code | **None** — zero implementation |
| Config | **None** — no `AI_PROTECTOR_MODE` env var, no `rollout_mode` field |
| Gate behavior | Always enforces — pre-tool gate always BLOCKs, no observe/warn bypass |
| Documentation | `07-rollout-modes.md` — full spec (385 lines) |

#### Definition of Done

- [ ] **Mode enum:** `observe | warn | enforce` (strict is v2)
- [ ] **Agent field:** `rollout_mode` on Agent model, default `observe`
- [ ] **API:** `PATCH /agents/:id` to change rollout mode
- [ ] **API:** `POST /agents/:id/promote` with from/to/reason
- [ ] **Pre-tool gate behavior:**
  - `observe` → log decision, allow through (adds `would_block: true` to trace)
  - `warn` → log decision, send alert, allow through
  - `enforce` → block/redact as implemented today
- [ ] **Post-tool gate behavior:** Same 3 modes for redaction decisions
- [ ] **Trace tagging:** Every trace includes `rollout_mode` field showing which mode was active
- [ ] **Stats API:** `GET /agents/:id/stats` returns observe-mode stats (would-be-blocked count, false positive rate)
- [ ] **Promotion readiness:** `GET /agents/:id/promotion-readiness` checks criteria (min days, FP rate, latency)
- [ ] **UI — Rollout tab:** Mode selector (observe/warn/enforce), promotion readiness checklist, stats, promote/rollback buttons
- [ ] **UI — Wizard step 7:** Set initial rollout mode (defaults to observe)
- [ ] **Test:** Set agent to observe → trigger block → tool call proceeds → trace shows `would_block: true`; switch to enforce → same trigger → tool call blocked

---

### Req 7: Traces with decision + reason

User must see: what tool, what role, what blocked it, was output redacted, which policy fired.

#### Current state

| Aspect | Status |
|--------|--------|
| TraceAccumulator | **Full** — `trace/accumulator.py` (257 lines), records all gate decisions |
| TraceStore | **Full** — `trace/store.py` (164 lines), in-memory LRU with filtering |
| Langfuse export | **Full** — `trace/langfuse.py` (183 lines), structured spans |
| API | **Full** — `GET /agent/traces`, `GET /agent/traces/{id}`, `GET /agent/traces/{id}/export` |
| Frontend — traces page | **Full** — `pages/agent-traces.vue` with table, filters, detail expansion |
| Frontend — trace panel | **Full** — `components/agent/trace-panel.vue` with real-time sidebar |
| Persistence | **In-memory only** — traces lost on restart |

#### Definition of Done

- [ ] **Already working (verify):**
  - Trace shows tool name, role, decision (ALLOW/BLOCK/REDACT), reason, risk score
  - Trace shows which pre-tool check triggered (RBAC/injection/args/limits/confirmation)
  - Trace shows post-tool actions (PII redacted, secrets found, injection in output, size truncated)
  - Trace panel shows in real-time during agent chat
  - Trace list page with filters (role, date, has_blocks)
  - Langfuse export with structured spans
- [ ] **Per-agent filtering:** Traces page filters by agent_id (currently all traces from one demo agent)
- [ ] **Rollout mode in trace:** Each trace includes `rollout_mode` field (depends on Req 6)
- [ ] **PostgreSQL persistence:** Traces stored in DB — at minimum agent_id, session_id, role, decision summary, risk_score, timestamp, and a JSONB column for the full trace payload. If Agents is a product pillar, in-memory traces create a "demo-like" perception that undermines trust. Basic DB persistence is required for v1, not optional.
- [ ] **Global Traces page:** Accessible from sidebar, shows traces across all agents
- [ ] **Agent Detail → Traces tab:** Shows traces for that specific agent only
- [ ] **Test:** Send agent request → trace appears in UI within 1s → all fields populated → export JSON matches

---

## What is explicitly NOT in v1

| Feature | Why not |
|---------|---------|
| Super rozbudowany policy builder | Policies section exists, enough for v1 |
| Full policy-as-code (Git sync) | Nice-to-have, not blocking product truth |
| Multi-team governance | Single-team is fine for v1 |
| Advanced analytics | Basic stats per agent are enough |
| HA / scaling | Single-instance Docker is fine for v1 |
| 10+ framework integrations | LangGraph + raw Python + proxy-only = enough |
| Red Team engine | Separate pillar, not needed for agent protection |
| Strict rollout mode | observe/warn/enforce is enough for v1 |
| Auto-import OpenAI function schemas | Manual tool registration is fine |
| ML-based attack detection | Regex/rule-based is enough for v1 |

---

## Summary matrix

| # | Requirement | Code | UI | End-to-end | Effort |
|---|------------|------|----|-----------|--------|
| 1 | Agent registration | None | None | **No** | Medium |
| 2 | Tools + roles | Full (YAML) | None | **Partial** | Medium |
| 3 | Generated config | Partial | Policy only | **Partial** | Medium |
| 4 | Integration kit | Full (ref impl) | None | **Partial** | Large |
| 5 | Attack validation | Full | Manual only | **Partial** | Medium |
| 6 | Rollout modes | None | None | **No** | Large |
| 7 | Traces | Full | Full | **Yes** | Small (filtering) |

### What works today

- All gate logic (pre-tool, post-tool, RBAC, limits, validation, PII, secrets, injection)
- Full trace pipeline with real-time UI
- Attack scenarios panel (manual)
- Policy CRUD
- Agent demo as reference implementation

### What must be built

- Agent CRUD API + DB model
- Tool/role CRUD API + DB model
- Config generation from agent profile
- Integration kit packaging/download
- Automated validation runner
- Rollout mode logic in gates
- "Agents" section in sidebar + wizard + detail pages

---

## Biggest product risk

The risk is not in the backend. The risk is building CRUD + tables + wizard + generators and still not delivering the real moment: "I plugged this in and my agent is actually protected."

v1 must obsessively guard three things:

### A. Integration kit works for real

Not just a preview in the UI — real files that the user downloads, drops into their project, and they work. If the generated `test_security.py` doesn't pass when the user runs `pytest`, the product has failed.

### B. Validation gives real feedback

Not just "pass 12/12" — the user must see what happened and why. A failed test must explain: what attack was tried, what was expected, what actually happened, and what to change. A passing test must show the gate decision trail.

### C. Rollout doesn't block adoption

Observe mode must work smoothly. If a user has to choose between "hard block everything" and "no protection", most will choose no protection. The observe → warn → enforce gradient is what makes enterprises say yes.

---

## Existing Agent Demo

The current Agent Demo (`/agent`) becomes:

**Option A (recommended):** Agents → Demo Agent — listed as a pre-configured reference agent in the Agents list, non-deletable, marked as "Reference Implementation"

**Option B:** Separate "Showcase" section — risk of confusing demo with real onboarding

The demo agent code in `apps/agent-demo/` remains the reference implementation that all generated integration kits are based on.

---

## Implementation order

Priority: reach the magic moment ("user can secure an agent") as fast as possible. Rollout modes are important but not the first magic moment — config → kit → validation is.

1. **Agent CRUD + DB** (Req 1) — everything else hangs on this
2. **Tools + Roles CRUD** (Req 2) — needed for config generation
3. **Config generation** (Req 3) — depends on 1+2, first tangible output
4. **Integration kit** (Req 4) — depends on 3, **highest risk item** — this is where user either gets value or bounces
5. **Validation runner** (Req 5) — depends on 4, completes the magic moment ("paste code → run test → see BLOCKED")
6. **Rollout modes** (Req 6) — important for adoption, but user already has value from steps 3-5
7. **Trace per-agent filtering + DB persistence** (Req 7) — depends on 1+6
8. **Frontend: Agents section + wizard** — parallel with backend, depends on APIs

> **Rationale for rollout after validation:** If time is tight, it's better to ship config + kit + validation first (user can secure an agent) and add rollout modes immediately after (user can deploy safely). Rollout without a working kit is useless; a working kit without rollout is still valuable (user just deploys in enforce mode).

---

## Documentation reference

Detailed implementation guides for each step:

| Step | Doc | Content |
|------|-----|---------|
| 1 | [01-describe-agent.md](agents-implementation/01-describe-agent.md) | Questionnaire, risk classification, API spec |
| 2 | [02-register-tools.md](agents-implementation/02-register-tools.md) | Tool inventory, schemas, smart defaults |
| 3 | [03-generate-rbac.md](agents-implementation/03-generate-rbac.md) | RBAC generation rules, permission matrix |
| 4 | [04-policy-packs.md](agents-implementation/04-policy-packs.md) | 5 pre-built policy presets |
| 5 | [05-integration-kit.md](agents-implementation/05-integration-kit.md) | Per-framework code generation |
| 6 | [06-attack-validation.md](agents-implementation/06-attack-validation.md) | 7 attack categories, test packs |
| 7 | [07-rollout-modes.md](agents-implementation/07-rollout-modes.md) | 4 modes, promotion, false positives |
| 8 | [08-traces-incidents.md](agents-implementation/08-traces-incidents.md) | Dashboards, incidents, alerting |
| ref | [ref/](agents-implementation/ref/) | Deep-dive technical reference (RBAC, gates, validation, limits) |
