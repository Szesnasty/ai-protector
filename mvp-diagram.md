# AI Protector — MVP Implementation Diagram

> 19 steps across 6 phases. Each step builds on the previous.
> ✅ = done, 🔜 = next, ⬜ = planned.

---

## Phase Overview

```
 Phase 1: Foundation          Phase 2: Firewall Pipeline       Phase 3: Agent Demo
┌─────────────────────┐     ┌──────────────────────────┐     ┌─────────────────────────┐
│ ✅ 01  Scaffolding   │     │ ✅ 06  Pipeline Core      │     │ ✅ 11  Agent Demo App    │
│ ✅ 02  Infrastructure│────▶│ ✅ 07  Security Scanners  │────▶│ ✅ 12  Agent ↔ Firewall  │
│ ✅ 03  Proxy Service │     │ ✅ 08  Policy Engine      │     │ ✅ 13  Agent Demo UI     │
│ ✅ 04  LLM Proxy     │     │ ✅ 09  Output Pipeline    │     └─────────────────────────┘
│ ✅ 05  Frontend Shell│     │ ✅ 10  Playground UI      │               │
└─────────────────────┘     └──────────────────────────┘               ▼
                                                          Phase 4: Custom Security Rules
                                                          ┌─────────────────────────┐
                                                          │ 🔜 14a Model & CRUD API │
                                                          │ ⬜ 14b Pipeline Integr.  │
                                                          │ ⬜ 14c Frontend Editor   │
                                                          └────────────┬────────────┘
                                                                       ▼
                                                          Phase 5: Dashboard & Data
                                                          ┌─────────────────────────┐
                                                          │ ⬜ 15  Policies & Log UI │
                                                          │ ⬜ 16  Analytics          │
                                                          └────────────┬────────────┘
                                                                       ▼
                                                            Phase 6: Harden & Ship
                                                          ┌─────────────────────────┐
                                                          │ ⬜ 17  MLJudge + NeMo    │
                                                          │ ⬜ 18  Rate Limit/Cache  │
                                                          │ ⬜ 19  Docs & Demo       │
                                                          └─────────────────────────┘
```

---

## Step Details

### Phase 1: Foundation ✅

| Step | Name | What it does | Status |
|------|------|-------------|--------|
| 01 | **Project Scaffolding** | Monorepo (`apps/proxy-service`, `apps/frontend`, `apps/agent-demo`), linters, configs | ✅ Done |
| 02 | **Infrastructure** | Docker Compose: PostgreSQL 16, Redis 7, Ollama, Langfuse — one `docker compose up` | ✅ Done |
| 03 | **Proxy Service Foundation** | FastAPI skeleton, SQLAlchemy models, Alembic migrations, health endpoint, seed data | ✅ Done |
| 04 | **Basic LLM Proxy** | `POST /v1/chat/completions` → Ollama via LiteLLM, SSE streaming, request logging | ✅ Done |
| 05 | **Frontend Shell** | Nuxt 4 + Vuetify 3 layout, navigation drawer, dark/light theme, health indicator | ✅ Done |

### Phase 2: Firewall Pipeline ✅

| Step | Name | What it does | Status |
|------|------|-------------|--------|
| 06 | **Pipeline Core** | LangGraph `StateGraph`, `ParseNode`, `IntentNode`, `RulesNode`, denylist service | ✅ Done |
| 07 | **Security Scanners** | LLM Guard (injection, toxicity, secrets) + Presidio PII detection, parallel execution | ✅ Done |
| 08 | **Policy Engine** | `PolicyDecisionNode`, 4 levels (fast/balanced/strict/paranoid), CRUD API + Redis cache | ✅ Done |
| 09 | **Output Pipeline** | `OutputFilterNode` (PII/secrets/leak redaction), `MemoryHygiene`, `LoggingNode` (Postgres + Langfuse) | ✅ Done |
| 10 | **Playground UI** | Chat interface with streaming, policy selector, debug panel (decision, intent, risk) | ✅ Done |

### Phase 3: Agent Demo ✅

| Step | Name | What it does | Status |
|------|------|-------------|--------|
| 11 | **Agent Demo App** | LangGraph agent: `IntentClassifier → PolicyCheck → ToolRouter`, 3 tools, RBAC | ✅ Done |
| 12 | **Agent ↔ Firewall** | Agent calls `proxy-service` via LiteLLM, session memory, mock KB + orders | ✅ Done |
| 13 | **Agent Demo UI** | Copilot chat, role selector, tool call annotations, agent trace panel | ✅ Done |

### Phase 4: Custom Security Rules 🔜

| Step | Name | What it does | Status |
|------|------|-------------|--------|
| 14a | **Model & CRUD API** | SecurityRule ORM, Alembic migration, OWASP LLM Top 10 + PII/PL seed categories, REST CRUD | 🔜 Next |
| 14b | **Pipeline Integration** | RulesNode reads custom rules, DenylistHit, flag/score_boost, intent override | ⬜ Planned |
| 14c | **Frontend Rules Editor** | Presets dropdown, auto-fill, data table, filters, create/edit/delete dialogs | ⬜ Planned |

### Phase 5: Dashboard & Data ⬜

| Step | Name | What it does | Status |
|------|------|-------------|--------|
| 15 | **Policies & Log UI** | Policies CRUD interface, request log with pagination, filters, expandable rows | ⬜ Planned |
| 16 | **Analytics** | KPI cards, timeline chart, block rate by policy, top risk flags, intent distribution | ⬜ Planned |

### Phase 6: Harden & Ship ⬜

| Step | Name | What it does | Status |
|------|------|-------------|--------|
| 17 | **MLJudge + NeMo** | `MLJudgeNode` (LLM-as-judge via Ollama), NeMo Guardrails integration, canary tokens | ⬜ Planned |
| 18 | **Rate Limit & Cache** | Redis rate limiting, decision caching for repeated prompts | ⬜ Planned |
| 19 | **Docs & Demo** | `securing-agents.md` (Level 0/1/2), README with setup, screenshots, demo GIF | ⬜ Planned |

---

## Data Flow Diagram

How a request travels through the system once all steps are complete:

```
┌──────────┐     ┌──────────────┐     ┌─────────────────────────────────────────────────────────┐
│  User /  │     │   Frontend   │     │                    Proxy Service                        │
│  Client  │────▶│  (Nuxt 4)    │────▶│  POST /v1/chat/completions                             │
└──────────┘     │  Step 05/10  │     │                                                         │
                 └──────────────┘     │  ┌─────────────────────────────────────────────────┐    │
                                      │  │           LangGraph Firewall Pipeline            │    │
                                      │  │                                                  │    │
                                      │  │  ┌───────┐   ┌────────┐   ┌───────┐   ┌──────┐ │    │
                                      │  │  │ Parse │──▶│ Intent │──▶│ Rules │──▶│Scann.│ │    │
                                      │  │  │  06   │   │  06    │   │  06   │   │  07  │ │    │
                                      │  │  └───────┘   └────────┘   └───────┘   └──┬───┘ │    │
                                      │  │                                          ▼      │    │
                                      │  │                                    ┌──────────┐ │    │
                                      │  │                                    │ Decision │ │    │
                                      │  │                                    │    08    │ │    │
                                      │  │                                    └────┬─────┘ │    │
                                      │  │                          ┌──────────┬───┴───┐   │    │
                                      │  │                          ▼          ▼       ▼   │    │
                                      │  │                       BLOCK     MODIFY   ALLOW  │    │
                                      │  │                          │    Transform    │    │    │
                                      │  │                          │       │         │    │    │
                                      │  │                          │    LLM Call  LLM Call│    │
                                      │  │                          │       │         │    │    │
                                      │  │                          │  OutputFilter OutputF│    │
                                      │  │                          │       │         │    │    │
                                      │  │                          └───┬───┘─────────┘    │    │
                                      │  │                              ▼                   │    │
                                      │  │                        ┌──────────┐              │    │
                                      │  │                        │ Logging  │──▶ Postgres  │    │
                                      │  │                        │   09c    │──▶ Langfuse  │    │
                                      │  │                        └──────────┘              │    │
                                      │  └──────────────────────────────────────────────────┘    │
                                      └─────────────────────────────────────────────────────────┘
                                                          │
                                      ┌─────────────────────────────────────────────────────────┐
                                      │                 Agent Demo (Step 11-12)                  │
                                      │                                                         │
                                      │  ┌──────────┐  ┌─────────────┐  ┌───────────────────┐  │
                                      │  │ Intent   │─▶│ Policy      │─▶│ Tool Router       │  │
                                      │  │Classifier│  │ Check       │  │ (KB/Orders/Email) │  │
                                      │  └──────────┘  └──────┬──────┘  └───────────────────┘  │
                                      │                        │                                │
                                      │               Uses proxy-service                        │
                                      │             as LLM backend (LiteLLM)                    │
                                      └─────────────────────────────────────────────────────────┘
```

---

## Pipeline Node Breakdown (Steps 06–09)

Each node is a Python `async` function decorated with `@timed_node`:

```
 Input Pipeline (Step 06)           Scanners (Step 07)         Decision (Step 08)
┌────────────────────────┐    ┌──────────────────────────┐   ┌────────────────────┐
│ ParseNode              │    │ parallel_scanners_node   │   │ PolicyDecisionNode │
│ ├─ extract user msg    │    │ ├─ LLM Guard             │   │ ├─ weight flags    │
│ ├─ compute prompt hash │───▶│ │  ├─ injection          │──▶│ ├─ sum risk_score  │
│ └─ load policy config  │    │ │  ├─ toxicity           │   │ ├─ compare threshold│
│                        │    │ │  └─ secrets             │   │ └─ ALLOW/MODIFY/   │
│ IntentNode             │    │ └─ Presidio PII           │   │    BLOCK           │
│ ├─ classify intent     │    │    ├─ email, phone, SSN   │   └────────────────────┘
│ └─ confidence score    │    │    └─ flag or mask         │
│                        │    └──────────────────────────┘
│ RulesNode              │
│ ├─ denylist check      │     Output Pipeline (Step 09)
│ ├─ length limit        │    ┌──────────────────────────┐
│ └─ encoding detection  │    │ OutputFilterNode  (09a)  │
└────────────────────────┘    │ ├─ PII redaction         │
                              │ ├─ secret redaction      │
                              │ └─ system leak detection │
                              │                          │
                              │ MemoryHygiene   (09b)    │
                              │ └─ sanitize conversation │
                              │                          │
                              │ LoggingNode      (09c)   │
                              │ ├─ Postgres audit row    │
                              │ └─ Langfuse trace+spans  │
                              │                          │
                              │ Graph Integration (09d)  │
                              │ └─ all paths → logging   │
                              └──────────────────────────┘
```

---

## Policies (Step 08)

Four built-in policy levels control the pipeline behavior:

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │                        Policy Levels                                │
 │                                                                      │
 │   fast          balanced        strict          paranoid             │
 │   ────          ────────        ──────          ────────             │
 │   Threshold:    Threshold:      Threshold:      Threshold:           │
 │   0.9           0.7             0.5             0.3                  │
 │                                                                      │
 │   Scanners:     Scanners:       Scanners:       Scanners:            │
 │   (none)        LLM Guard       LLM Guard       LLM Guard            │
 │                                  Presidio        Presidio             │
 │                                                                      │
 │   Nodes:        Nodes:          Nodes:          Nodes:               │
 │   (minimal)     output_filter   output_filter   output_filter        │
 │                  logging         memory_hygiene  memory_hygiene       │
 │                                  logging         logging              │
 │                                                                      │
 │   Use case:     Use case:       Use case:       Use case:            │
 │   Dev/testing   Production      Regulated data  Maximum security     │
 └──────────────────────────────────────────────────────────────────────┘
```

---

## Test Coverage

```
325 tests passing (pytest)
 ├── Pipeline nodes .................. ~120 tests
 │   ├── parse, intent, rules ........ 35
 │   ├── scanners (LLM Guard + Presidio) 45
 │   ├── decision node ............... 20
 │   ├── output filter ............... 12
 │   └── logging node ................ 12
 ├── Integration (full pipeline) ..... ~40 tests
 │   ├── graph routing ............... 3
 │   ├── ALLOW/BLOCK/MODIFY E2E ...... 10
 │   └── graph with mocked LLM ...... 6
 ├── Services ........................ ~30 tests
 │   ├── request logger .............. 10
 │   ├── langfuse client ............. 8
 │   └── denylist, policy cache ...... 12
 ├── API endpoints ................... ~25 tests
 │   ├── chat completions ............ 11
 │   ├── policies CRUD ............... 14
 │   └── health ...................... 2
 └── Schemas & utils ................ ~20 tests
```

---

*Generated from [MVP-PLAN.md](docs/plan/MVP-PLAN.md). Last updated: 2026-03-03.*
