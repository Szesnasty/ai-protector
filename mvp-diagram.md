# AI Protector — MVP Implementation Diagram

> 20 steps across 7 phases. Each step builds on the previous.
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
                                                          │ ✅ 14a Model & CRUD API  │
                                                          │ ✅ 14b Pipeline Integr.  │
                                                          │ ✅ 14c Frontend Editor   │
                                                          └────────────┬────────────┘
                                                                       ▼
                                                          Phase 5: Dashboard & Data
                                                          ┌─────────────────────────┐
                                                          │ ✅ 15  Policies & Log UI │
                                                          │ ✅ 16  Analytics          │
                                                          └────────────┬────────────┘
                                                                       ▼
                                                          Phase 6: Enterprise Readiness
                                                          ┌─────────────────────────┐
                                                          │ ⬜ 17  Observe/Simulate  │
                                                          │ ⬜ 18  Explainability    │
                                                          │ ⬜ 19  Replay Requests   │
                                                          └────────────┬────────────┘
                                                                       ▼
                                                          Phase 7: Demo & Polish
                                                          ┌─────────────────────────┐
                                                          │ ✅ 20  Attack Scenarios  │
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

### Phase 4: Custom Security Rules ✅

| Step | Name | What it does | Status |
|------|------|-------------|--------|
| 14a | **Model & CRUD API** | SecurityRule ORM, Alembic migration, OWASP LLM Top 10 + PII/PL seed categories, REST CRUD | ✅ Done |
| 14b | **Pipeline Integration** | RulesNode reads custom rules, DenylistHit, flag/score_boost, intent override | ✅ Done |
| 14c | **Frontend Rules Editor** | Presets dropdown, auto-fill, data table, filters, create/edit/delete dialogs | ✅ Done |

### Phase 5: Dashboard & Data ✅

| Step | Name | What it does | Status |
|------|------|-------------|--------|
| 15 | **Policies & Log UI** | Policies CRUD interface, request log with pagination, filters, expandable rows | ✅ Done |
| 16 | **Analytics** | KPI cards, timeline chart (ECharts), block rate by policy, top risk flags, intent distribution, sub-minute polling | ✅ Done |

### Phase 6: Enterprise Readiness ⬜

| Step | Name | What it does | Status |
|------|------|-------------|--------|
| 17 | **Observe / Simulate** | Per-policy observe mode: BLOCK → ALLOW in shadow, logs `original_decision` for audit | ⬜ Spec written |
| 18 | **Explainability** | Structured explanation for every decision: matched rules, scanner signals, risk breakdown | ⬜ Spec written |
| 19 | **Replay Requests** | Replay any log entry through pipeline with different policy, side-by-side comparison | ⬜ Spec written |

### Phase 7: Demo & Polish ✅

| Step | Name | What it does | Status |
|------|------|-------------|--------|
| 20 | **Attack Scenarios Panel** | 260 ready-made attack prompts (157 Playground + 103 Agent), skull FAB, one-click auto-submit, tag filter, OWASP labels | ✅ Done |

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
348 tests (pytest)
 ├── Pipeline nodes .................. ~140 tests
 │   ├── parse, intent, rules ........ 45
 │   ├── scanners (LLM Guard + Presidio) 50
 │   ├── decision node ............... 22
 │   ├── output filter ............... 12
 │   └── logging node ................ 14
 ├── Integration (full pipeline) ..... ~50 tests
 │   ├── graph routing ............... 5
 │   ├── ALLOW/BLOCK/MODIFY E2E ...... 12
 │   └── graph with mocked LLM ...... 8
 ├── Services ........................ ~50 tests
 │   ├── request logger .............. 14
 │   ├── custom rules CRUD ........... 20
 │   ├── langfuse client ............. 8
 │   └── denylist, policy cache ...... 12
 ├── API endpoints ................... ~40 tests
 │   ├── chat completions ............ 14
 │   ├── policies CRUD ............... 14
 │   ├── analytics ................... 8
 │   └── health ...................... 2
 └── Schemas & utils ................ ~30 tests
```

---

*Generated from [MVP-PLAN.md](docs/plan/MVP-PLAN.md). Last updated: 2026-03-03.*
