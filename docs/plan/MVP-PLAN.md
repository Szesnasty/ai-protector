# MVP Implementation Plan

> Spec-driven development: each step has its own folder with detailed docs and a Definition of Done.
> Check off items as they are completed. Work through steps sequentially — each builds on the previous.

---

## Phase 1: Foundation (week 1–2)

- [x] **[Step 01 — Project Scaffolding](01-project-scaffolding/SPEC.md)**
  Monorepo structure, linters, Python & Node configs, .gitignore

- [x] **[Step 02 — Infrastructure (Docker Compose)](02-infrastructure/SPEC.md)**
  All services: PostgreSQL, Redis, Ollama, Langfuse — one `docker compose up`

- [x] **[Step 03 — Proxy Service Foundation](03-proxy-foundation/SPEC.md)**
  FastAPI skeleton, SQLAlchemy models, Alembic migrations, health endpoint, seed data

- [x] **[Step 04 — Basic LLM Proxy](04-basic-llm-proxy/SPEC.md)**
  `POST /v1/chat/completions` passthrough to Ollama via LiteLLM, streaming support

- [x] **[Step 05 — Frontend Foundation](05-frontend-foundation/SPEC.md)**
  Nuxt 4 + Vuetify 4 shell: layout, navigation drawer, dark/light theme, health indicator, Axios + Vue Query API layer

## Phase 2: Firewall Pipeline (week 3–4)

- [x] **[Step 06 — Pipeline Core (LangGraph)](06-pipeline-core/SPEC.md)**
  ParseNode + IntentNode + RulesNode, LangGraph state & graph wiring

- [x] **[Step 07 — Security Scanners](07-security-scanners/SPEC.md)**
  LLM Guard (injection, toxicity, secrets) + Presidio PII detection — parallel scanner nodes

- [x] **[Step 08 — Policy Engine](08-policy-engine/SPEC.md)**
  PolicyDecisionNode, 4 policy levels (fast/balanced/strict/paranoid), policies CRUD API

- [x] **[Step 09 — Output Pipeline](09-output-pipeline/SPEC.md)**
  OutputFilterNode (PII/secrets/leak redaction), MemoryHygieneNode, LoggingNode (Postgres + Langfuse), graph integration

- [x] **[Step 10 — Frontend: Playground](10-playground-ui/SPEC.md)**
  Chat UI with streaming, policy selector, debug panel (decision, intent, risk, flags)

## Phase 3: Agent Demo (week 5–6)

- [x] **[Step 11 — Agent Demo App](11-agent-demo-app/SPEC.md)**
  LangGraph agent: IntentClassifier → PolicyCheck → ToolRouter, 3 tools, role-based access

- [x] **[Step 12 — Agent ↔ Firewall Integration](12-agent-firewall-integration/SPEC.md)**
  Agent calls proxy-service via LiteLLM, session memory, mock data (KB + orders)

- [x] **[Step 13 — Frontend: Agent Demo UI](13-agent-demo-ui/SPEC.md)**
  Copilot chat, role selector, tool call annotations, agent trace panel

## Phase 4: Custom Security Rules (week 6)

- [x] **[Step 14 — Custom Security Rules](14-custom-security-rules/SPEC.md)**
  OWASP LLM Top 10 + PII/PL preset categories, rules CRUD API, pipeline integration, frontend Rules Editor
  - [x] [14a — Model, Migration & CRUD API](14-custom-security-rules/14a-model-migration-crud.md)
  - [x] [14b — Pipeline Integration](14-custom-security-rules/14b-pipeline-integration.md)
  - [x] [14c — Frontend Rules Editor](14-custom-security-rules/14c-frontend-rules-editor.md)

## Phase 5: Dashboard & Data (week 7)

- [x] **[Step 15 — Frontend: Policies & Request Log](15-policies-request-log/SPEC.md)**
  Policies CRUD UI, request log with server-side pagination, filters, expandable rows
  - [x] [15a — Request Log API](15-policies-request-log/15a-request-log-api.md)
  - [x] [15b — Policies CRUD UI](15-policies-request-log/15b-policies-ui.md)
  - [x] [15c — Request Log UI](15-policies-request-log/15c-request-log-ui.md)

- [x] **[Step 16 — Frontend: Analytics](16-analytics/SPEC.md)**
  KPI cards, timeline chart, block rate by policy, top risk flags, intent distribution
  - [x] [16a — Analytics API](16-analytics/16a-analytics-api.md)
  - [x] [16b — KPI Cards & Timeline](16-analytics/16b-kpi-timeline.md)
  - [x] [16c — Breakdown Panels](16-analytics/16c-breakdowns.md)

## Phase 6: Enterprise Readiness (week 7–8)

- [ ] **[Step 17 — Observe / Simulate Mode](17-observe-simulate/SPEC.md)**
  Per-policy observe mode: pipeline runs fully but BLOCK → ALLOW; logs `original_decision` for audit.
  Shows enterprise deployment maturity — teams validate policies on live traffic before enforcing.
  - [ ] 17a — Policy model `mode` column + migration
  - [ ] 17b — Pipeline mode-gate node (after decision)
  - [ ] 17c — Request model: `original_decision` + `mode` columns, API filters
  - [ ] 17d — Frontend: policy toggle, "would block" chips, observe analytics

- [ ] **[Step 18 — Explainability](18-explainability/SPEC.md)**
  Structured explanation for every decision: which rules matched, which scanners triggered,
  per-signal risk breakdown, threshold comparison. Critical for compliance & developer trust.
  - [ ] 18a — ExplainNode + decomposed `calculate_risk_breakdown()`
  - [ ] 18b — `explanation` JSONB column, persistence, API
  - [ ] 18c — Frontend: risk breakdown bar, matched rules, threshold gauge

- [ ] **[Step 19 — Replay Requests](19-replay-requests/SPEC.md)**
  Click any log entry → replay through pipeline with different policy/model → side-by-side
  comparison of decisions. Zero LLM cost (pre-LLM pipeline only). Powerful for policy tuning.
  - [ ] 19a — `POST /v1/requests/{id}/replay` endpoint + comparison schema
  - [ ] 19b — `messages_json` persistence in Request model (opt-in)
  - [ ] 19c — Comparison builder with delta computation
  - [ ] 19d — Frontend: replay dialog, side-by-side diff view

## Phase 7: Demo & Polish

- [x] **[Step 20 — Attack Scenarios Panel](20-attack-scenarios-panel/SPEC.md)**
  Floating side panel with **260 ready-made attack prompts** (157 Playground + 103 Agent) covering
  injection, jailbreak, PII, exfil, toxicity, tool abuse, role bypass, system prompt leaking,
  cognitive hacking, misinformation, few-shot manipulation, excessive agency, resource exhaustion,
  multi-turn escalation, chain-of-thought attacks. One click → auto-submit. Tag filter + OWASP labels.
  Both Playground & Agent Demo. Skull FAB toggle, panels collapsed by default.
  - [x] 20a — Types + scenario data (14 Playground groups / 157 prompts, 12 Agent groups / 103 prompts)
  - [x] 20b — `AttackScenariosPanel.vue` component (search, tag filter, grouped buttons, decision chips)
  - [x] 20c — Playground integration (toggle, auto-send, chat input expose)
  - [x] 20d — Agent Demo integration (toggle, auto-send, chat input expose)

## Phase 8: OSS Maturity

- [x] **[Step 21 — OSS Maturity & Project Hygiene](21-oss-maturity/SPEC.md)**
  Transform the repo into a credible open-source project: LICENSE, community files,
  CI/CD, security scanning, Dependabot, badges, release tagging.
  - [x] 21a — MIT License
  - [x] 21b — Community files (CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, issue/PR templates)
  - [x] 21c — GitHub Actions CI (ci.yml, codeql.yml, dependency-review.yml)
  - [x] 21d — Dependabot configuration
  - [x] 21e — Fix failing unit tests (13 tests — missing mocks + wrong DenylistHit types)
  - [x] 21f — README badges (CI, CodeQL, License, Python, Nuxt)
  - [ ] 21g — First release tag v0.1.0
  - [ ] 21h — Branch protection rules (GitHub UI)
  - [ ] 21i — Repository settings polish (topics, social preview, discussions)

---

## Progress

| Phase | Steps | Status |
|-------|-------|--------|
| Foundation | 01–05 | 🟩 01 02 03 04 05 done |
| Firewall Pipeline | 06–09 | 🟩 06 07 08 09 done |
| Playground UI | 10 | 🟩 10 done |
| Agent Demo | 11–13 | 🟩 11 12 13 done |
| Custom Rules | 14 | 🟩 14a 14b 14c done |
| Dashboard | 15–16 | 🟩 15 16 done |
| Enterprise Readiness | 17–19 | ⬜ Not started (specs written) |
| Demo & Polish | 20 | 🟩 20 done |
| OSS Maturity | 21 | 🟨 21a-f done, 21g-i pending (GitHub UI) |

---

*Each step folder contains a `SPEC.md` with detailed tasks, technical decisions, and Definition of Done.*
*Steps link to each other with prev/next for easy navigation.*
