# AI Protector — Post-MVP Roadmap

> Everything below is out of MVP scope. Features are grouped into phases, roughly ordered by priority and dependency.

---

## Phase 0: Agents v1 (immediate next)

> **Full spec:** [`agents-v1.spec.md`](agents-v1.spec.md)

New product pillar: **Agents** — registration, tool/role RBAC, config generation, integration kit, attack validation, rollout modes, traces.

| # | Requirement | Status |
|---|------------|--------|
| 1 | Agent registration (profile, risk level) | Not started |
| 2 | Tools + roles CRUD (RBAC, default-deny, confirmation) | Backend exists (YAML), no API/UI |
| 3 | Generated config (rbac.yaml, limits, policy pack) | Not started |
| 4 | Integration kit (pre/post gate, snippets, tests) | Reference code exists, no generator |
| 5 | Attack validation runner | Gate logic works, no automated runner |
| 6 | Observe / Warn / Enforce rollout modes | Not started |
| 7 | Traces with decision + reason | Working (needs per-agent filtering + DB persistence) |

**Implementation order:** Agent CRUD → Tools/Roles → Config generation → Integration kit → Validation → Rollout modes → Traces

**Key risk:** Integration kit is the core product — must generate real, working files, not just previews.

---

## Phase 1: Red Team Lab (weeks 9–14)

The second pillar of AI Protector. Transforms the project from "just a firewall" into a full **offensive + defensive AI security platform**.

### 1.1. Red Team Attack Engine

| Feature | Description |
|---------|-------------|
| **Attack Campaigns** | Named attack sessions with target policy, model, and goal |
| **garak SDK Integration** | Use garak (LLM vulnerability scanner) as the core attack library |
| **Attack Types** | Prompt injection (direct, indirect), jailbreak (DAN, AIM, role-play), PII extraction, system prompt leak, multi-turn escalation, hallucination probing |
| **LangGraph Attack Agent** | Agentic attacker: plans strategy → selects technique → executes → evaluates → adapts |
| **Campaign Dashboard** | Progress, success/fail matrix, technique effectiveness, timeline |

### 1.2. Red Team Agent Architecture

```
┌─────────────────────────────────────────────────────┐
│  Red Team Attack Agent (LangGraph)                  │
│                                                     │
│  PlanNode → TechniqueSelector → PayloadGenerator    │
│         → ExecuteNode → EvaluateNode → AdaptNode    │
│                              │                      │
│                              ▼                      │
│                    ┌──────────────────┐              │
│                    │  Attacks go      │              │
│                    │  through the     │              │
│                    │  proxy-service   │              │
│                    │  (Blue Team)     │              │
│                    └──────────────────┘              │
│                                                     │
│  ReportNode → generates findings + recommendations  │
└─────────────────────────────────────────────────────┘
```

### 1.3. Attack Library

| Category | Techniques |
|----------|-----------|
| Prompt Injection | Direct instruction override, indirect (via context), delimiter confusion, encoding (base64, ROT13) |
| Jailbreak | DAN, AIM, role-play ("you are a hacker"), multi-persona, hypothetical framing |
| Data Extraction | System prompt leak attempts, PII fishing, canary token extraction, training data extraction |
| Multi-turn | Gradual trust building, context poisoning, history manipulation, topic drift escalation |
| Tool Abuse | Attempt to call restricted tools, parameter injection, tool chaining exploits |
| Encoding | Unicode homoglyphs, zero-width chars, markdown injection, HTML entities |

### 1.4. Key Deliverables

- [ ] Attack campaign CRUD (API + UI)
- [ ] garak integration (selected probes)
- [ ] LangGraph attack agent (basic strategy)
- [ ] Report generation (per-campaign results)
- [ ] Red Team dashboard in frontend
- [ ] Red vs Blue comparison view

---

## Phase 2: Advanced Blue Team (weeks 15–18)

### 2.1. Adaptive Policies

- **Auto-escalation**: if block rate spikes, automatically tighten policy (balanced → strict)
- **Client reputation scores**: clients with history of blocked requests get higher scrutiny
- **Time-based policies**: stricter after hours, relaxed during business hours
- **Policy versioning**: full history, diff view, rollback

### 2.2. Advanced Agent Security

> **Note:** The foundation for agent management is being built in **Agents v1** (Phase 0). Items marked ✅ below are addressed there. This phase covers the advanced features that build on top of v1.

| Feature | Description | Agents v1? |
|---------|-------------|------------|
| **Multi-agent support** | Multiple agents with different configs behind one proxy | ✅ Agent registration + per-agent config |
| **Agent fingerprinting** | Identify which agent made each request (by client-id patterns) | ✅ agent_id on every request/trace |
| **Tool-call auditing** | Log every tool call with parameters, not just LLM calls | ✅ Full trace with tool calls + gate decisions |
| **Cross-agent correlation** | Detect coordinated attacks across multiple agents | Phase 2 — needs multi-agent data first |
| **Agent health scoring** | Dashboard panel showing per-agent risk profile over time | ✅ Partial — validation scorecard + trace stats |

### 2.3. Session/Memory Agent

| Feature | Description |
|---------|-------------|
| **Session context tracking** | Track full conversation context across turns |
| **Memory poisoning detection** | Detect gradual injection via multi-turn conversations |
| **Context window management** | Smart truncation that preserves security-relevant history |
| **Session risk escalation** | Risk score increases as session shows suspicious patterns |
| **Automatic session termination** | Kill sessions that exceed risk thresholds |

### 2.4. NeMo Guardrails Deep Integration

- Colang 2.0 flows for complex dialog patterns
- Custom actions for domain-specific checks
- Programmable dialog rails (e.g., refuse to generate code if policy says so)
- Topic control (prevent off-topic conversations)

---

## Phase 3: Enterprise Features (weeks 19–24)

### 3.1. Multi-Tenancy

- Tenant isolation: separate policies, logs, analytics per tenant
- API key management per tenant
- Tenant-specific LLM routing (different models per org)
- Usage quotas and billing foundations

### 3.2. Advanced Analytics

| Feature | Description |
|---------|-------------|
| **Attack timeline** | Combined Red + Blue view over time |
| **Policy effectiveness** | Which policies catch what, miss rates |
| **Cost tracking** | Token usage → dollar amounts, per-tenant |
| **Latency optimization** | Pipeline heatmap: which nodes are bottlenecks |
| **Export** | CSV/PDF reports with date range filters |

### 3.3. Advanced Dashboard

- **Live mode**: WebSocket real-time request feed
- **Custom dashboards**: drag-and-drop widget layout
- **Alert rules**: email/webhook notifications on risk spikes
- **Comparison view**: side-by-side Red Team vs Blue Team metrics
- **Incident timeline**: narrative view of security events

### 3.4. Authentication & Authorization

- OAuth 2.0 / OIDC integration (Keycloak, Auth0)
- RBAC: admin, analyst, viewer roles in dashboard
- API key scopes (read-only, full access)
- Audit log for all admin actions

---

## Phase 4: Scale & Optimize (weeks 25+)

### 4.1. Performance

- **Async pipeline execution**: parallel scanner nodes
- **Decision caching**: Redis cache for repeated/similar prompts
- **Model optimization**: quantized models for ML Judge
- **Batch processing**: handle concurrent requests efficiently
- **Connection pooling**: optimized DB and Redis connections

### 4.2. Vector Capabilities

- **Semantic similarity**: use pgvector for fuzzy denylist matching
- **Embedding cache**: store prompt embeddings for duplicate detection
- **RAG protection**: secure retrieval-augmented generation pipelines
- **Knowledge base search**: vector-powered KB for agent demo

### 4.3. Integration Ecosystem

| Integration | Purpose |
|-------------|---------|
| **OpenAI** | Direct API routing (not just Ollama) |
| **Anthropic / Claude** | Multi-provider support via LiteLLM |
| **AWS Bedrock** | Enterprise LLM provider |
| **Slack** | Alert notifications |
| **PagerDuty** | Incident management |
| **Grafana** | Advanced metrics visualization |
| **SIEM** | Security event export (Splunk, Elastic) |

---

## Phase 5: Community & Open Source (ongoing)

### 5.1. Plugin Architecture

- Custom scanner plugins (npm/pip packages)
- Policy template marketplace
- Attack technique contributions
- Guardrail recipe sharing

### 5.2. Documentation & Education

| Deliverable | Description |
|-------------|-------------|
| **securing-agents.md** | Core doc: Level 0/1/2 comparison (MVP) |
| **cookbook** | Recipe-style guides for common scenarios |
| **attack-catalog** | Documented attack types with examples |
| **benchmark results** | Firewall accuracy vs known attack datasets |
| **video walkthrough** | Full demo recording for portfolio |

### 5.3. Testing & Quality

- Automated benchmark suite (attack corpus → measure detection rate)
- Policy regression tests (ensure policy changes don't break security)
- Load testing (locust or k6)
- E2E tests (Playwright for frontend)

---

## Priority Matrix

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| Red Team basic attacks | 🔴 High | Medium | P1 |
| Red Team LangGraph agent | 🔴 High | High | P1 |
| Adaptive policies | 🟡 Medium | Medium | P2 |
| Multi-agent support | 🟡 Medium | Low | P2 |
| Session risk tracking | 🔴 High | Medium | P2 |
| Multi-tenancy | 🟡 Medium | High | P3 |
| Real-time dashboard | 🟡 Medium | Medium | P3 |
| Auth/RBAC | 🟡 Medium | Medium | P3 |
| Vector search / RAG | 🟡 Medium | Medium | P3 |
| Plugin architecture | 🟢 Low | High | P4 |
| SIEM integration | 🟢 Low | Medium | P4 |

---

## Tech Debt & Improvements

- [ ] Unit test coverage > 80%
- [ ] Integration tests for full pipeline
- [ ] API versioning (v1 → v2)
- [ ] OpenAPI spec generation + client SDKs
- [ ] CI/CD: GitHub Actions (lint, test, build, push images)
- [ ] Helm chart for Kubernetes deployment
- [ ] Monitoring: Prometheus + Grafana stack
- [ ] Database: read replicas for analytics queries
