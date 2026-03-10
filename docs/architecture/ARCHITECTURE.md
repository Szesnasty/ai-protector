# Architecture

> Internal reference for contributors and security reviewers.
> For a quickstart see [README.md](../README.md).

---

## System overview

AI Protector is a two-level security layer for LLM-powered applications:

```
                         ┌─────────────────────────────────┐
                         │          Frontend (Nuxt 4)       │
                         │  Playground · Analytics · Agent  │
                         └──────────┬──────────┬───────────┘
                                    │          │
                         ┌──────────▼──┐  ┌────▼───────────┐
                         │ Proxy API   │  │  Agent Demo    │
                         │ (FastAPI)   │  │  (FastAPI)     │
                         │ port 8000   │  │  port 8002     │
                         └──────┬──────┘  └───────┬────────┘
                                │                 │
                    ┌───────────▼─────────────────▼───────────┐
                    │          PostgreSQL (pgvector/pg16)      │
                    │              Redis 7                     │
                    └─────────────────────────────────────────┘
                                │
                    ┌───────────▼─────────────────────────────┐
                    │     LLM Provider (LiteLLM routing)      │
                    │  OpenAI · Anthropic · Google · Ollama …  │
                    └─────────────────────────────────────────┘
```

---

## Level 1 — Proxy firewall

The proxy service sits between the client application and the LLM provider.
Every request passes through a **9-node LangGraph pipeline** before and after the model call.

### Pipeline graph

```
parse → intent → rules → scanners → decision
                                       ├─ BLOCK  → logging → END
                                       ├─ MODIFY → transform → llm_call → output_filter → logging → END
                                       └─ ALLOW  → llm_call → output_filter → logging → END
```

### Node responsibilities

| Node | Purpose |
|------|---------|
| **ParseNode** | Validate & normalize the incoming OpenAI-format request |
| **IntentNode** | Classify user intent (benign, injection, jailbreak, social engineering, …) |
| **RulesNode** | Evaluate denylist phrases, custom regex/keyword rules |
| **ScannersNode** | Run scanner backends in parallel (Presidio, LLM Guard, NeMo Guardrails) |
| **DecisionNode** | Aggregate risk scores, apply policy thresholds → BLOCK / MODIFY / ALLOW |
| **TransformNode** | Redact or rewrite the prompt before forwarding (MODIFY path only) |
| **LLMCallNode** | Forward the (possibly transformed) request to the LLM provider via LiteLLM |
| **OutputFilterNode** | Post-process LLM response: PII redaction, secrets stripping, system prompt leak detection |
| **LoggingNode** | Persist the full request trace to PostgreSQL and optionally to Langfuse |

### Scanner backends

| Scanner | Detects |
|---------|---------|
| **Presidio** (Microsoft) | PII: names, emails, phone numbers, credit cards, SSN, 10 entity types |
| **LLM Guard** (Protect AI) | Prompt injection, jailbreak, toxicity, encoded attacks |
| **NeMo Guardrails** (NVIDIA) | Dialog policy violations, topic drift, off-topic requests |

### Firewall policies

Four built-in policies with different risk tolerance:

| Policy | `max_risk` | `injection_threshold` | `pii_action` |
|--------|-----------|----------------------|---------------|
| fast | 0.8 | 0.7 | warn |
| balanced | 0.5 | 0.4 | block |
| strict | 0.3 | 0.2 | block |
| paranoid | 0.15 | 0.1 | block |

Custom policies can be created via the REST API.

---

## Level 2 — Agent guardrails

The agent demo (Customer Support Copilot) shows in-agent security controls.
It uses a separate **LangGraph state machine** with 11 nodes.

### Scan + LLM call architecture

The agent uses a two-step approach for LLM calls:

1. **Step 1 — Firewall scan:** Call the proxy's `POST /v1/scan` endpoint with `scan_messages` (user message only) for security analysis (injection detection, PII scanning, policy evaluation). This is a lightweight scan-only call — no LLM inference happens.
2. **Step 2 — LLM call:** If the scan allows the request, send the full message history (system prompt, tool results, conversation context) directly to the LLM provider via LiteLLM.

This separates security enforcement from LLM inference — the proxy never sees tool results or the system prompt, while user input is always scanned. The `/v1/scan` endpoint runs the same `run_pre_llm_pipeline()` as the full proxy path, ensuring identical security coverage with minimal latency.

### Agent graph

```
input → intent → policy_check → tool_router
                                    ├─ (no tools) → llm_call → response → memory → END
                                    └─ (tools)    → pre_tool_gate
                                                       ├─ blocked     → llm_call → …
                                                       ├─ confirm     → confirmation_response → memory → END
                                                       └─ allowed     → tool_executor → post_tool_gate → llm_call → …
```

### Agent security controls

| Control | Mechanism |
|---------|-----------|
| **RBAC** | Role → tool allowlist (YAML config). Default-deny. |
| **Pre-tool gate** | Check role permissions + argument schema before execution |
| **Post-tool gate** | Scan tool output for PII / secrets before returning to LLM |
| **Argument validation** | JSON Schema per tool — reject malformed or out-of-range args |
| **Confirmation flows** | Sensitive tools (e.g. `issueRefund`) require user approval |
| **Budget limits** | Per-session caps: max tokens, max tool calls, max cost |

### RBAC roles (default config)

| Role | Inherits | Tools | Sensitivity |
|------|----------|-------|-------------|
| customer | — | `searchKnowledgeBase`, `getOrderStatus` | low |
| support | customer | + `getCustomerProfile` | medium |
| admin | support | + `getInternalSecrets`, `issueRefund` | critical |

---

## Data layer

| Store | Purpose |
|-------|---------|
| **PostgreSQL** (pgvector/pg16) | Policies, denylist phrases, custom rules, request logs, analytics |
| **Redis 7** | Rate limiting, session cache, pub/sub for config publish notifications |

### Key models

- `Policy` — firewall policy with JSON config (thresholds, scanner toggles)
- `DenylistPhrase` — blocked phrases/regex patterns linked to policies
- `CustomRule` — user-defined rules with conditions and actions
- `RequestLog` — full audit trail of every proxied request

---

## Frontend

Nuxt 4 + Vuetify 4 single-page application.

| Page | Purpose |
|------|---------|
| Dashboard | System overview, recent activity |
| Playground | Chat through the firewall with real-time risk scoring |
| Agent Demo | Interactive agent with role selector and tool call visualization |
| Analytics | Charts: blocked vs allowed, risk distribution, timeline, intent breakdown |
| Attack Scenarios | 350+ one-click attacks organized by OWASP category |
| Policies | CRUD for firewall policies and denylist phrases |
| Rules | Custom rule management |
| Settings | API key management, model selection, policy defaults |
| Request Log | Searchable audit trail with filtering |
| Compare | Side-by-side playground for policy comparison |

---

## Deployment

### Docker Compose profiles

| Profile | Services | Use case |
|---------|----------|----------|
| `demo` | proxy, agent-demo, frontend, PostgreSQL, Redis | Evaluation, demos (mock LLM) |
| `full` | All demo + Ollama, Langfuse, model-pull | Development, production |

### Port allocation

| Port | Service |
|------|---------|
| 3000 | Frontend |
| 8000 | Proxy API |
| 8002 | Agent Demo API |
| 3001 | Langfuse (full profile only) |
| 5432 | PostgreSQL |
| 6379 | Redis |
| 11434 | Ollama (full profile only) |

---

## CI pipeline

GitHub Actions workflow (`ci.yml`):

```
lint-python ──────┐
lint-frontend ────┤
test-proxy ───────┼──► (all must pass)
test-agent ───────┤
build-frontend ───┤
docker-build ─────┘
```

- **lint-python**: ruff check + ruff format for proxy-service and agent-demo
- **test-proxy**: pytest with PostgreSQL + Redis services, coverage reporting (1 050 tests)
- **test-agent**: pytest (in-memory, no external services) (421 tests)
- **docker-build**: builds all 3 Docker images

Additional workflows:
- **release.yml**: Release Please (automated versioning, v0.1.0+)
- **codeql.yml**: CodeQL security analysis (Python + JavaScript, weekly schedule)

All actions are pinned to full-length commit SHAs.
Pre-commit hooks enforce ruff check/format and Conventional Commits locally.

---

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| LangGraph over middleware chain | Stateful graph enables conditional routing (BLOCK/MODIFY/ALLOW), parallel scanner execution, and clear node boundaries |
| Deterministic enforcement | No LLM-as-judge — security decisions are made by rules, scanners, and thresholds; reproducible and auditable |
| LiteLLM for provider routing | Single proxy endpoint works with 6+ providers; no vendor lock-in |
| Separate proxy + agent layers | Proxy catches network-level threats; agent layer catches tool-use threats; defense in depth |
| PostgreSQL for everything | Single data store for policies, logs, analytics; pgvector ready for future embedding search |
| Session-scoped API keys | Keys stay in browser (sessionStorage); server never persists them |

---

## What's next

The MVP is complete (all phases except Phase 6 Enterprise). The **primary focus** is now
**Agents v1** — transforming the agent demo into a full product pillar:

1. Agent registration (profile, risk level, recommended preset)
2. Tools & roles CRUD with generated RBAC config
3. Integration kit — 7 copy-paste files to protect any agent in 60 minutes
4. Attack validation runner
5. Traces & incidents with per-agent filtering

See [ROADMAP](../ROADMAP.spec.md) and [Agents Implementation Guides](../agents-implementation/README.md) for details.

---

## Detailed pipeline references

| Doc | What |
|-----|------|
| [PROXY_FIREWALL_PIPELINE.md](PROXY_FIREWALL_PIPELINE.md) | Full 9-node proxy graph — node internals, risk score formula, scanner model table |
| [AGENT_PIPELINE.md](AGENT_PIPELINE.md) | Full 11-node agent graph — pre/post-gate checks, three lines of defense |
