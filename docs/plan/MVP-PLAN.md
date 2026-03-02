# MVP Implementation Plan

> Spec-driven development: each step has its own folder with detailed docs and a Definition of Done.
> Check off items as they are completed. Work through steps sequentially — each builds on the previous.

---

## Phase 1: Foundation (week 1–2)

- [ ] **[Step 01 — Project Scaffolding](01-project-scaffolding/SPEC.md)**
  Monorepo structure, linters, Python & Node configs, .gitignore

- [ ] **[Step 02 — Infrastructure (Docker Compose)](02-infrastructure/SPEC.md)**
  All services: PostgreSQL, Redis, Ollama, Langfuse — one `docker compose up`

- [ ] **[Step 03 — Proxy Service Foundation](03-proxy-foundation/SPEC.md)**
  FastAPI skeleton, SQLAlchemy models, Alembic migrations, health endpoint, seed data

- [ ] **Step 04 — Basic LLM Proxy**
  `POST /v1/chat/completions` passthrough to Ollama via LiteLLM, streaming support

- [ ] **Step 05 — Frontend Foundation**
  Nuxt 4 + Vuetify 3 shell: layout, navigation drawer, dark/light theme, health indicator

## Phase 2: Firewall Pipeline (week 3–4)

- [ ] **Step 06 — Pipeline Core (LangGraph)**
  ParseNode + IntentNode + RulesNode, LangGraph state & graph wiring

- [ ] **Step 07 — Security Scanners**
  LLM Guard (injection, toxicity, secrets) + Presidio PII detection — parallel scanner nodes

- [ ] **Step 08 — Policy Engine**
  PolicyDecisionNode, 4 policy levels (fast/balanced/strict/paranoid), policies CRUD API

- [ ] **Step 09 — Output Pipeline**
  PromptTransformNode, OutputFilterNode, MemoryHygieneNode, LoggingNode (Postgres + Langfuse)

- [ ] **Step 10 — Frontend: Playground**
  Chat UI with streaming, policy selector, debug panel (decision, intent, risk, flags)

## Phase 3: Agent Demo (week 5–6)

- [ ] **Step 11 — Agent Demo App**
  LangGraph agent: IntentClassifier → PolicyCheck → ToolRouter, 3 tools, role-based access

- [ ] **Step 12 — Agent ↔ Firewall Integration**
  Agent calls proxy-service via LiteLLM, session memory, mock data (KB + orders)

- [ ] **Step 13 — Frontend: Agent Demo UI**
  Copilot chat, role selector, tool call annotations, agent trace panel

## Phase 4: Dashboard & Data (week 6–7)

- [ ] **Step 14 — Frontend: Policies & Request Log**
  Policies CRUD UI, request log with server-side pagination, filters, expandable rows

- [ ] **Step 15 — Frontend: Analytics**
  KPI cards, timeline chart, block rate by policy, top risk flags, intent distribution

## Phase 5: Harden & Ship (week 7–8)

- [ ] **Step 16 — MLJudge & Advanced Scanners**
  MLJudgeNode (LLM-as-judge via Ollama), NeMo Guardrails integration, canary tokens

- [ ] **Step 17 — Rate Limiting & Caching**
  Redis rate limiting, decision caching for repeated prompts

- [ ] **Step 18 — Docs & Demo**
  `securing-agents.md` (Level 0/1/2), README with setup guide, screenshots, demo GIF

---

## Progress

| Phase | Steps | Status |
|-------|-------|--------|
| Foundation | 01–05 | ⬜ Not started |
| Firewall Pipeline | 06–09 | ⬜ Not started |
| Playground UI | 10 | ⬜ Not started |
| Agent Demo | 11–13 | ⬜ Not started |
| Dashboard | 14–15 | ⬜ Not started |
| Harden & Ship | 16–18 | ⬜ Not started |

---

*Each step folder contains a `SPEC.md` with detailed tasks, technical decisions, and Definition of Done.*
*Steps link to each other with prev/next for easy navigation.*
