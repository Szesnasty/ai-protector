# Red Team — Technical Handoff

> Working document for the next developer/assistant: what problem the red-team module solves, what already works, where regressions lurk, and what to do next.

---

## Business Context (Problem)

Red Team / Wizard must call **any** external customer backend — not just one canonical chat format (OpenAI `messages`).

| Problem | Impact |
|---------|--------|
| Proxy runs in a container — `localhost` points inside the container | `ConnectionRefused` to the service on the host machine |
| Default body `{"messages":[…]}` → 4xx on APIs with custom DTOs | Model is never invoked; scan results are misleading |
| No upstream response diagnostics on errors | User cannot tell *what* failed validation |
| HTTP client timeout < API orchestration timeout | Browser cuts off before server responds |
| Scan request template lost on navigation | Scan falls back to default shape without custom body |
| Responses are non-standard JSON | Normalizer heuristics miss the meaningful text |

---

## Current State — What Is Implemented

### 1. Container vs Local Host

| File | What it does |
|------|-------------|
| [`apps/proxy-service/src/red_team/net.py`](../../apps/proxy-service/src/red_team/net.py) | `rewrite_localhost_for_docker()` — replaces `localhost`/`127.0.0.1`/`::1` with `host.docker.internal` when the process sees `/.dockerenv` |
| same file | `validate_url()` — SSRF validation (scheme, hostname, private IP); in Docker: private addresses blocked except `host.docker.internal` |
| [`adapters.py`](../../apps/proxy-service/src/red_team/engine/adapters.py) L55 | `RealHttpClient.send_prompt()` — rewrites URL via `rewrite_localhost_for_docker` before sending |
| [`routes.py`](../../apps/proxy-service/src/red_team/api/routes.py) L274-278 | Test-connection — rewrite + URL validation, `resolved_url` in response |

### 2. Test Connection

| File | What it does |
|------|-------------|
| [`routes.py`](../../apps/proxy-service/src/red_team/api/routes.py) L264-340 | `POST /v1/benchmark/test-connection` — ping target, handles 401/403/4xx/5xx/timeout/SSL, returns `error_code` |
| [`api/__init__.py`](../../apps/proxy-service/src/red_team/api/__init__.py) L140-160 | `TestConnectionRequest` — `endpoint_url`, `custom_headers`, `auth_header` (legacy), `timeout_s` |
| same file | `TestConnectionResponse` — `status`, `status_code`, `latency_ms`, `content_type`, `error`, `error_code`, `resolved_url` |
| [`RedTeamTargetForm.vue`](../../apps/frontend/app/components/RedTeamTargetForm.vue) L382-440 | Frontend: connection test gating, `humanizeConnectionError()`, non-JSON warning |

### 3. Scan — Request & Target Configuration

**`target_config` keys** (verified by grepping the codebase):

| Key | Type | Set by | Used in |
|-----|------|--------|---------|
| `endpoint_url` | `str` | frontend → query param | `adapters.py`, `routes.py` |
| `timeout_s` | `int` | frontend (default 30) | `adapters.py`, `run_engine.py` |
| `agent_type` | `str` | frontend radio (`chatbot_api` / `tool_calling`) | `run_engine.py`, `worker.py` (pack filtering) |
| `safe_mode` | `bool` | frontend toggle | `run_engine.py`, `worker.py` (scenario skip) |
| `target_name` | `str?` | frontend | UI label |
| `environment` | `str?` | frontend (hosted only) | reporting |
| `benchmark_role` | `str` | not in UI (default `"customer"`) | `adapters.py` (demo agent payload) |
| `custom_headers` | `dict` | frontend → ephemeral store | `worker.py` → encryption → `_decrypted_headers` |
| `auth_secret_ref` | `str` | service layer (after encryption) | `worker.py` (decryption) |
| `through_proxy` | `bool` | not in UI | `worker.py` (`ProtectedHttpClient` wrapper) |
| `_decrypted_headers` | `dict` | runtime (worker) | `adapters.py` (HTTP headers) |
| `_decrypted_auth` | `str` | runtime (worker, legacy) | `adapters.py` (fallback header) |
| `_system_prompt` | `str?` | not in UI | `adapters.py` (system message) |
| `request_template` | `str?` | frontend (advanced settings) | `adapters.py` (custom request body) |
| `response_text_paths` | `list[str]?` | frontend (advanced settings) | `adapters.py` → `json_text_extractor` |

### 4. Scan — Payload Construction

Current logic in `RealHttpClient.send_prompt()` ([adapters.py](../../apps/proxy-service/src/red_team/engine/adapters.py) L54-88):

```
if request_template exists in target_config:
    render template with {{ATTACK_PROMPT}} / {{SYSTEM_PROMPT}}
elif "/agent/chat" in endpoint_url:
    payload = {message, role, session_id}     # demo agent format
else:
    payload = {messages: [{role, content}]}   # OpenAI-style fallback
```

### 5. Scan — Response Normalization

Logic in `SimpleNormalizer.normalize()` ([adapters.py](../../apps/proxy-service/src/red_team/engine/adapters.py)):

```
if response_text_paths configured:
    body_text = json_text_extractor(parsed_json, paths)
if not body_text:
    body_text = heuristic (6 well-known keys: response, output_text, message, content, text, output)
if not body_text:
    body_text = raw body
```

### 6. Frontend — Configuration Flow

| File | Role |
|------|------|
| [`target.vue`](../../apps/frontend/app/pages/red-team/target.vue) | Form: URL, headers, connection test → `emit('continue', config)` |
| [`RedTeamTargetForm.vue`](../../apps/frontend/app/components/RedTeamTargetForm.vue) | Form component (endpoint, headers, safe mode, timeouts, request template, response paths) |
| [`useEphemeralHeaders.ts`](../../apps/frontend/app/composables/useEphemeralHeaders.ts) | In-memory store: `stash()` / `take()` / `clear()` — never written to disk |
| [`useScanConfig.ts`](../../apps/frontend/app/composables/useScanConfig.ts) | SessionStorage-backed store for request template + response paths across navigation |
| [`configure.vue`](../../apps/frontend/app/pages/red-team/configure.vue) | Pack/policy selection → `POST /v1/benchmark/runs` → redirect to `/red-team/run/:id` |

---

## Definition of Done

- [ ] Test-connection accepts custom body (optional JSON instead of hardcoded `{"messages":[…]}`)
- [ ] Upstream error on test-connection shows a body snippet for diagnostics
- [ ] Scan uses request template when present in `target_config`
- [ ] Request template supports `{{ATTACK_PROMPT}}` placeholder (and optionally `{{SYSTEM_PROMPT}}`)
- [ ] `response_text_paths` in `target_config` → normalizer assembles meaningful `body_text`
- [ ] Fallback to raw body works when paths miss
- [ ] `localhost` → `host.docker.internal` in container, no rewrite in native mode
- [ ] Old integrations (`demo`, `chatbot_api` without template) are not broken
- [ ] Unit tests for: custom body connection, template rendering, path extraction, normalizer with paths

---

## Most Sensitive Areas (Regression Watch)

| Area | Risk | File(s) |
|------|------|---------|
| URL validation vs runtime | SSRF bypass if rewrite changes semantics; private IPs in Docker allowed only for `host.docker.internal` | `net.py` |
| Payload branching | Three paths (demo agent / template / OpenAI fallback) — easy to break dispatch | `adapters.py` L54-88 |
| Ephemeral headers ↔ target_config | Headers live in JS memory; `take()` clears after first read; if user navigates differently — headers are lost | `useEphemeralHeaders.ts`, `configure.vue` L396 |
| Normalizer fallback chain | Configured paths → heuristic (6 keys) → raw body — order and priority matter | `adapters.py` `SimpleNormalizer` |
| Timeouts FE ↔ API ↔ HTTP client | Three layers: axios (frontend) → FastAPI endpoint timeout → httpx client timeout. Client ≤ API ≤ FE, otherwise truncation | `benchmarkService.ts`, `routes.py`, `adapters.py` |
| Privacy in run listings | `target_config` in API response — large templates and paths visible, headers masked | `api/routes.py`, `DbPersistenceAdapter.get_run()` |

---

## What To Do Next — Prioritized

### P1 — Request Transport (request template)

**Problem**: `RealHttpClient.send_prompt()` knows only two formats (demo agent, OpenAI messages). APIs with custom DTOs get 4xx.

**Plan**:
1. New key `target_config.request_template` — JSON string with `{{ATTACK_PROMPT}}` and `{{SYSTEM_PROMPT}}` placeholders
2. In `RealHttpClient.send_prompt()`: if template exists → render via `str.replace` → `json.loads` → send; otherwise → current logic
3. **Extensibility**: keys `request_method` (default POST), `request_content_type` (default `application/json`), `request_query_params` — without breaking old runs (optional fields, old runs lack these keys)
4. Frontend: textarea in advanced settings (after test-connection), option to "use test body as template" with `{{ATTACK_PROMPT}}` validation
5. Tests: template rendering, missing placeholder error, backward compat (no template → old flow)

### P1 — Response Text Extraction (response paths)

**Problem**: `SimpleNormalizer` guesses the key (`response`, `output_text`, `message`…) — for non-standard DTOs it extracts nothing useful.

**Plan**:
1. New key `target_config.response_text_paths` — list of paths: `["data.result.text", "data.items.*.content"]`
2. New module `json_text_extractor.py` — walk path (split `.`, `*` = iterate array), collect fragments, join with `\n`
3. In `SimpleNormalizer.normalize()`: if paths → extractor; fallback to heuristic; fallback to raw body
4. **Extensibility**: consider JSONPath (`jmespath` / `jsonpath-ng`) in the future, but start with simple subset
5. Frontend: JSON paths field in advanced settings, hint "Use dot notation, * for arrays"
6. Tests: nested key, array wildcard, missing key fallback, empty paths → heuristic, malformed JSON → raw body

### P2 — Scenarios for DTO APIs

**Problem**: Many scenarios assume natural-language refusal ("I cannot help with that"). APIs returning only structured JSON (e.g., `{"error": "forbidden"}`) → refusal_pattern detectors miss → misleading results.

**Plan**:
1. Pack variant or tag `response_format: structured` on scenarios
2. New detectors: `json_field_check` (e.g., `error` field present = refusal), `status_code_check`
3. Documentation: "For APIs that don't respond in natural language, use these detectors"

### P2 — Network Documentation

**Problem**: Docker Compose users don't know when to enter `http://my-service:8080` (orchestration network) vs `http://localhost:8080` vs `http://host.docker.internal:8080`.

**Plan**:
1. Docs section: "Connecting to your endpoint from AI Protector"
2. Table: launch mode (native / Docker / Docker Compose) × service location (same host / same network / external)
3. UI warning when URL = localhost and proxy is in a container: "This will be routed via host.docker.internal"

### P3 — Large Payload Privacy

**Problem**: `target_config` with request template and response paths is returned in the run-list API — large templates, potentially sensitive.

**Plan**:
1. Mask / trim `target_config` in list-runs (return only `endpoint_url`, `target_name`)
2. Full `target_config` only in detail view (`GET /runs/:id`)
3. In exports (JSON/markdown) warn about template sensitivity

---

## `target_config` Keys — Public Registry

Current keys read by the backend (verified by grepping the code):

```
target_config = {
  // --- set by frontend ---
  "endpoint_url":        str,    // target URL
  "timeout_s":           int,    // HTTP timeout (default 30)
  "agent_type":          str,    // "chatbot_api" | "tool_calling"
  "safe_mode":           bool,   // skip dangerous scenarios
  "target_name":         str?,   // label
  "environment":         str?,   // "staging" | "internal" | "production_like"
  "custom_headers":      dict?,  // headers (encrypted before persistence)
  "request_template":    str?,   // JSON template with {{ATTACK_PROMPT}}
  "response_text_paths": list?,  // ["data.text", "items.*.content"]

  // --- set by backend ---
  "auth_secret_ref":  str?,   // ref to encrypted credentials
  "through_proxy":    bool?,  // ProtectedHttpClient wrapper
  "benchmark_role":   str?,   // demo agent role (default "customer")

  // --- runtime (never persisted) ---
  "_decrypted_headers": dict?, // decrypted headers
  "_decrypted_auth":    str?,  // legacy single header
  "_system_prompt":     str?,  // system message for payload

  // --- PLANNED (future) ---
  // "request_method":        str?,   // "POST" (default) | "PUT" | "PATCH"
  // "request_content_type":  str?,   // "application/json" (default)
  // "request_query_params":  dict?,  // ?key=val
}
```

---

## Flow Diagram (Current State)

```
┌──────────────┐  query params + scan  ┌────────────────┐
│  target.vue  │  config (sessionStore) │ configure.vue  │
│  (form)      │ ─────────────────────→ │ (pack, policy) │
└──────────────┘  + ephemeral headers   └───────┬────────┘
                                                │ POST /v1/benchmark/runs
                                                │ {target_type, target_config, pack, policy}
                                                ▼
                                        ┌───────────────┐
                                        │  routes.py    │
                                        │  create_run() │
                                        └───────┬───────┘
                                                │ asyncio.create_task
                                                ▼
                                        ┌───────────────────┐
                                        │  worker.py        │
                                        │  decrypt headers  │
                                        │  choose client    │
                                        └──────┬────────────┘
                                               │
                                               ▼
                                        ┌───────────────────┐
                                        │  run_engine.py    │
                                        │  filter scenarios │
                                        │  loop: send →     │
                                        │  normalize →      │
                                        │  evaluate → score │
                                        └──────┬────────────┘
                              ┌────────────────┼────────────────┐
                              ▼                ▼                ▼
                       ┌──────────┐    ┌────────────┐   ┌───────────┐
                       │ adapters │    │ adapters   │   │ detectors │
                       │ send_    │    │ normalize()│   │ evaluate()│
                       │ prompt() │    │            │   │           │
                       └──────────┘    └────────────┘   └───────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │ Target endpoint  │
                       │ (demo / custom)  │
                       └──────────────────┘
```

---

## Continuation Prompt (paste forward)

```
You are a developer in the ai-protector repository.
Red team / wizard must support real integrations: arbitrary request and
response JSON, not just one open-standard chat format.

ALREADY DONE (preserve tests/docs, do not regress):
- Test connection: custom headers, error_code + status_code preview,
  custom body support, body_snippet in error responses,
  UI↔API timeouts, non-JSON warning.
- Proxy in container: rewrite_localhost_for_docker() in net.py;
  validate_url() with exception for host.docker.internal.
- Scan: request_template with {{ATTACK_PROMPT}} placeholder in
  target_config; payload branching (template → demo agent → OpenAI).
- Scan: response_text_paths in target_config — dot-notation paths
  with * for arrays; json_text_extractor module; normalizer uses
  paths → heuristic → raw body.
- Frontend: RedTeamTargetForm → target.vue → configure.vue flow
  with ephemeral headers (in-memory, take-and-clear) and useScanConfig
  (sessionStorage for template + paths).

REAL WORLD — REFINE (priority order):

P1) Request: additional headers, content type, query params;
    possibly non-POST — extensible transport contract without
    breaking old runs.

P1) Response: richer path language (e.g., full JSONPath) vs current
    subset; always sensible fallback to entire body.

P2) Scenario packs: many tests assume natural-language refusal —
    for APIs returning only DTOs this produces misleading results;
    consider pack variant or detectors for "structured-only response".

P2) Documentation: when user must enter orchestration-network
    service name instead of loopback address.

P3) Privacy: large templates and path lists in run-list API responses
    — consider masking / trimming.

Deliver brief integration docs and tests wherever logic grows.
Before working: search the repository for public target_config keys
(registry in docs/red-team/HANDOFF.md).
Do not create new target_config fields without updating the registry.
```
