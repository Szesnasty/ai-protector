# AI Protector — MVP Implementation Diagram

> 20 steps across 7 phases. **All core phases complete (1–5 + 7).**
> Next milestone: **Agents v1** — see [ROADMAP](docs/ROADMAP.spec.md).
>
> ✅ = done, ⬜ = planned (deferred to post-MVP).

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
                                                          Phase 6: Enterprise (deferred)
                                                          ┌─────────────────────────┐
                                                          │ ⬜ 17  Observe/Simulate  │
                                                          │ ⬜ 18  Explainability    │
                                                          │ ⬜ 19  Replay Requests   │
                                                          └────────────┬────────────┘
                                                                       ▼
                                                          Phase 7: Demo & Polish ✅
                                                          ┌─────────────────────────┐
                                                          │ ✅ 20  Attack Scenarios  │
                                                          └─────────────────────────┘

                                                                Next milestone
                                                          ┌─────────────────────────┐
                                                          │ 🔜 AGENTS v1            │
                                                          │    Agent registration   │
                                                          │    Tools/Roles CRUD     │
                                                          │    Config generation    │
                                                          │    Integration kit      │
                                                          │    Attack validation    │
                                                          │    Traces & incidents   │
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

### Phase 6: Enterprise Readiness ⬜ (deferred — focusing on Agents v1 first)

| Step | Name | What it does | Status |
|------|------|-------------|--------|
| 17 | **Observe / Simulate** | Per-policy observe mode: BLOCK → ALLOW in shadow, logs `original_decision` for audit | ⬜ Deferred |
| 18 | **Explainability** | Structured explanation for every decision: matched rules, scanner signals, risk breakdown | ⬜ Deferred |
| 19 | **Replay Requests** | Replay any log entry through pipeline with different policy, side-by-side comparison | ⬜ Deferred |

### Phase 7: Demo & Polish ✅

| Step | Name | What it does | Status |
|------|------|-------------|--------|
| 20 | **Attack Scenarios Panel** | 350+ ready-made attack prompts (Playground + Agent), skull FAB, one-click auto-submit, tag filter, OWASP labels | ✅ Done |

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
1 471 tests (pytest) — 1 050 proxy-service + 421 agent-demo
 ├── Proxy Service (1 050 tests)
 │   ├── Pipeline nodes .............. ~350 tests
 │   │   ├── parse, intent, rules ..... 90
 │   │   ├── scanners (LLM Guard + Presidio) 120
 │   │   ├── decision node ............ 60
 │   │   ├── output filter ............ 40
 │   │   └── logging node ............. 40
 │   ├── Integration (full pipeline) .. ~150 tests
 │   ├── Services (CRUD, cache) ....... ~200 tests
 │   ├── API endpoints ................ ~200 tests
 │   └── Schemas & utils .............. ~150 tests
 │
 └── Agent Demo (421 tests)
     ├── Agent graph nodes ............ ~120 tests
     ├── RBAC & gates ................. ~100 tests
     ├── Tool validation .............. ~80 tests
     ├── Limits & budgets ............. ~60 tests
     └── API & integration ............ ~60 tests
```

---

---

## What's Next: Agents v1

The MVP is complete. The main focus going forward is **Agents v1** —
transforming the agent demo into a full product pillar where users can
register their own agents, map tools and roles, generate guardrail
configs, and deploy them safely.

See:
- [ROADMAP — Agents v1](docs/ROADMAP.spec.md#phase-0-agents-v1-immediate-next)
- [Agents Implementation Guides](docs/agents-implementation/README.md)
- [Agents v1 Spec](docs/agents-v1.spec.md)

---

*Generated from [MVP-PLAN.md](docs/plan/MVP-PLAN.md). Last updated: 2026-03-09.*
