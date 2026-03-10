# Threat Model

> Application-layer threat model for AI Protector.
> For architecture details see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Assets

| Asset | Description | Sensitivity |
|-------|-------------|-------------|
| **User prompts** | Text sent by end-users through the proxy | High — may contain PII, business logic, internal data |
| **LLM responses** | Model outputs returned to users | High — may leak training data, system prompts, PII |
| **System prompts** | Instructions prepended by the application | Critical — reveals application logic, guardrails |
| **API keys** | LLM provider credentials | Critical — financial exposure, account takeover |
| **Firewall policies** | Threshold configs, denylist phrases, custom rules | Medium — knowledge enables bypass crafting |
| **Request logs** | Full audit trail of proxied requests | High — contains prompt/response content |
| **Agent tool outputs** | Data returned by tools (customer profiles, orders) | Medium–Critical — depends on tool sensitivity |
| **RBAC configuration** | Role-to-tool mappings | Medium — knowledge enables privilege escalation attempts |

---

## 2. Trust boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│  UNTRUSTED: User input (prompts, parameters, headers)          │
├─────────────────────────────────────────────────────────────────┤
│  BOUNDARY 1: Proxy API ingress (port 8000)                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  SEMI-TRUSTED: Firewall pipeline (parse → decision)      │  │
│  │  Deterministic enforcement — no LLM involved             │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  BOUNDARY 2: LLM provider call (outbound)                │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  EXTERNAL: LLM provider (OpenAI, Anthropic, …)     │  │  │
│  │  │  Response is untrusted — passes through output      │  │  │
│  │  │  filter before returning to user                    │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  BOUNDARY 3: Agent tool execution (port 8002)                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  CONTROLLED: Tool functions (searchKB, getOrder, …)      │  │
│  │  Gated by RBAC + pre-tool gate + argument validation     │  │
│  │  Output scanned by post-tool gate before returning       │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  TRUSTED: Database (PostgreSQL), Cache (Redis), Config files   │
│  Accessed only by backend services, not exposed externally     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Attacker goals

| Goal | Impact | OWASP LLM ID |
|------|--------|--------------|
| **Prompt injection** | Override system instructions, extract secrets | LLM01 |
| **Data exfiltration** | Extract PII, system prompts, training data via crafted prompts | LLM02, LLM06 |
| **Jailbreak** | Bypass safety filters to generate harmful/unrestricted content | LLM01 |
| **Tool abuse** | Invoke unauthorized tools, escalate privileges, perform actions beyond role | LLM07, LLM08 |
| **Denial of service** | Exhaust token budgets, flood requests, trigger expensive model calls | LLM04 |
| **Policy bypass** | Craft inputs that evade scanners while carrying malicious semantics | LLM01 |
| **Secret extraction** | Recover API keys, database credentials, internal endpoints | LLM06 |

---

## 4. Entry points

| Entry point | Protocol | Authentication | Rate limited |
|-------------|----------|----------------|--------------|
| `POST /v1/chat/completions` | HTTP/JSON | API key (passthrough) | By policy config |
| `POST /v1/chat/completions` (stream) | HTTP/SSE | API key (passthrough) | By policy config |
| `POST /v1/scan` | HTTP/JSON | API key (passthrough) | By policy config |
| `GET/POST /v1/policies/*` | HTTP/JSON | None (admin API) | No |
| `GET/POST /v1/rules/*` | HTTP/JSON | None (admin API) | No |
| `POST /agent/chat` | HTTP/JSON | Session-based | By budget limits |
| Frontend (port 3000) | HTTP | None | No |

---

## 5. Controls

### 5.1 Input pipeline (Proxy)

| Control | Threat mitigated | Implementation |
|---------|-----------------|----------------|
| **Intent classification** | Prompt injection, jailbreak, social engineering | Rule-based classifier with keyword + pattern matching |
| **Denylist rules** | Known attack patterns | Regex/keyword phrases linked to policies, individually toggleable |
| **LLM Guard scanner** | Injection, jailbreak, toxicity | ML-based classifier (runs locally, no external calls) |
| **Presidio PII scanner** | PII leakage in prompts | 10 entity types (names, emails, SSN, credit cards, …) |
| **NeMo Guardrails** | Dialog drift, off-topic, prohibited topics | Colang rail definitions |
| **Risk scoring** | Multi-signal decision | Weighted aggregation of scanner scores → policy threshold |
| **Request length limits** | Denial of service | Max message length, max message count per request |

### 5.2 Output pipeline (Proxy)

| Control | Threat mitigated | Implementation |
|---------|-----------------|----------------|
| **PII redaction** | PII in model responses | Presidio on output text |
| **Secrets stripping** | API keys, tokens in output | Pattern matching for common secret formats |
| **System prompt leak detection** | System prompt extraction | Heuristic check for system prompt content in response |

### 5.3 Agent controls

| Control | Threat mitigated | Implementation |
|---------|-----------------|----------------|
| **RBAC** | Unauthorized tool access | Role→tool allowlist (YAML), default-deny, role inheritance |
| **Pre-tool gate** | Tool misuse, argument injection | Permission check + JSON Schema argument validation |
| **Post-tool gate** | Data exfiltration via tools | PII/secrets scan on tool output before returning to LLM |
| **Confirmation flows** | Excessive agency | High-sensitivity tools require explicit user confirmation |
| **Budget limits** | Resource exhaustion | Per-session caps: max tokens, max tool calls, max cost |

### 5.4 Operational controls

| Control | Implementation |
|---------|----------------|
| **Audit logging** | Every request logged to PostgreSQL with full trace |
| **Langfuse tracing** | Optional distributed tracing for debugging |
| **API key isolation** | Keys stored in browser sessionStorage only; never logged or persisted server-side |
| **No telemetry** | No external calls for analytics or tracking |
| **CI enforcement** | Lint, tests, Docker build on every push; pre-commit hooks |

---

## 6. Residual risks

| Risk | Severity | Mitigation status | Notes |
|------|----------|-------------------|-------|
| **Novel semantic injection** | High | Partially mitigated | Pattern-based scanners cannot catch all novel attack phrasings. Defense-in-depth (3 scanner layers) reduces but does not eliminate risk. |
| **Scanner evasion via encoding** | Medium | Mitigated | LLM Guard covers common encoding tricks (base64, unicode). Novel encodings may bypass. |
| **Admin API unauthenticated** | Medium | Accepted (development scope) | Policy/rule CRUD endpoints have no auth. Production deployments must add authentication. |
| **Tool runtime behavior** | Medium | Partially mitigated | RBAC and argument validation gate *access*, but do not verify what a tool *actually does* at runtime. |
| **Single-node availability** | Low | Accepted | No HA or horizontal scaling. Acceptable for current scope. |
| **Provider-specific bypass** | Low | Accepted | Different LLM providers may respond differently to the same prompt. Policy tuning per model recommended. |
| **Prompt logging privacy** | Low | Configurable | Full prompts logged by default. Can be disabled or redacted via policy config. |
| **Database credential in config** | Low | Accepted (Docker scope) | Default credentials in docker-compose.yml. Production must use secrets management. |

---

## 7. Attack surface summary

```
                    UNTRUSTED INPUT
                         │
          ┌──────────────▼──────────────┐
          │  ParseNode (validation)     │ ← malformed JSON, oversized payloads
          │  IntentNode (classification)│ ← novel injection patterns
          │  RulesNode (denylist)       │ ← encoding evasion
          │  ScannersNode (ML + rules)  │ ← adversarial ML inputs
          │  DecisionNode (thresholds)  │ ← threshold tuning gaps
          └──────────────┬──────────────┘
                         │ ALLOW/MODIFY
          ┌──────────────▼──────────────┐
          │  LLM Provider (external)    │ ← provider behavior variance
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │  OutputFilterNode           │ ← novel PII formats, system prompt variants
          │  LoggingNode                │ ← log injection (mitigated by structured logging)
          └──────────────┬──────────────┘
                         │
                    RESPONSE TO USER
```

---

## 8. Content Security Policy

The frontend sets a strict CSP via Nitro server middleware (`server/middleware/security-headers.ts`).

| Directive | Value | Notes |
|-----------|-------|-------|
| `default-src` | `'self'` | Only same-origin resources |
| `script-src` | `'self' 'unsafe-inline'` | Nuxt hydration injects inline scripts; nonce support possible but not yet implemented |
| `style-src` | `'self' 'unsafe-inline'` | **Required by Vuetify** — runtime theme/component styles are injected as `<style>` tags; no nonce/hash workaround exists |
| `font-src` | `'self' data:` | MDI icons load as data URIs |
| `img-src` | `'self' data: blob:` | ECharts may render as blob URLs |
| `connect-src` | `'self'` + configured API bases + LLM provider domains | Built dynamically from `runtimeConfig` |
| `frame-ancestors` | `'none'` | Prevents clickjacking |
| `base-uri` | `'self'` | Prevents `<base>` tag injection |
| `form-action` | `'self'` | Prevents form hijacking |

**Why `unsafe-inline` is acceptable here:**
- AI Protector is a **self-hosted internal tool**, not a public-facing website
- The primary XSS vector (user-controlled content rendered without escaping) is handled by Vue's default template escaping
- Vuetify does not support nonce-based style injection — this is a framework limitation, not a configuration oversight
- Removing `unsafe-inline` from `script-src` is feasible via `nuxt-security` module + nonce injection, but ROI is low for an internal tool

---

## 9. Recommendations for production

1. **Add authentication** to admin API endpoints (policies, rules, analytics)
2. **Enable TLS** — terminate SSL at a reverse proxy (nginx, Caddy, cloud LB)
3. **Use secrets management** — replace docker-compose env vars with Vault/KMS/SSM
4. **Network segmentation** — keep proxy and database on private network
5. **Prompt logging policy** — configure redaction level appropriate for your compliance requirements
6. **Threshold calibration** — tune policy thresholds per domain and model to minimize false positives
7. **Monitor scanner updates** — keep LLM Guard, Presidio, NeMo Guardrails up to date for new attack patterns
8. **Rate limiting** — add request rate limits at the proxy or load balancer level
