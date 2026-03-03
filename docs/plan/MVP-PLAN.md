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

- [ ] **[Step 13 — Frontend: Agent Demo UI](13-agent-demo-ui/SPEC.md)**
  Copilot chat, role selector, tool call annotations, agent trace panel

## Phase 4: Custom Security Rules (week 6)

- [ ] **[Step 14 — Custom Security Rules](14-custom-security-rules/SPEC.md)**
  Rules CRUD API (action: block/flag/score_boost, severity), intent-aware matching, bulk import/export, frontend Rules Editor

## Phase 5: Dashboard & Data (week 7)

- [ ] **Step 15 — Frontend: Policies & Request Log**
  Policies CRUD UI, request log with server-side pagination, filters, expandable rows

- [ ] **Step 16 — Frontend: Analytics**
  KPI cards, timeline chart, block rate by policy, top risk flags, intent distribution

## Phase 6: Harden & Ship (week 7–8)

- [ ] **Step 17 — MLJudge & Advanced Scanners**
  MLJudgeNode (LLM-as-judge via Ollama), NeMo Guardrails integration, canary tokens

- [ ] **Step 18 — Rate Limiting & Caching**
  Redis rate limiting, decision caching for repeated prompts

- [ ] **Step 19 — Docs & Demo**
  `securing-agents.md` (Level 0/1/2), README with setup guide, screenshots, demo GIF

---

## Progress

| Phase | Steps | Status |
|-------|-------|--------|
| Foundation | 01–05 | 🟩 01 02 03 04 05 done |
| Firewall Pipeline | 06–09 | 🟩 06 07 08 09 done |
| Playground UI | 10 | 🟩 10 done |
| Agent Demo | 11–13 | 🟨 11 done, 12-13 pending |
| Custom Rules | 14 | ⬜ Spec ready |
| Dashboard | 15–16 | ⬜ Not started |
| Harden & Ship | 17–19 | ⬜ Not started |

---

*Each step folder contains a `SPEC.md` with detailed tasks, technical decisions, and Definition of Done.*
*Steps link to each other with prev/next for easy navigation.*
