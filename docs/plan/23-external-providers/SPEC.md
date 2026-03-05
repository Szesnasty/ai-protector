# Step 23 — External LLM Providers (Browser-Side Key Management)

| | |
|---|---|
| **Phase** | Multi-Provider Proxy |
| **Estimated time** | 6–8 hours |
| **Prev** | [Step 22 — NeMo Guardrails](../22-nemo-guardrails/SPEC.md) |
| **Next** | [Step 24 — Compare Playground](../24-compare-playground/SPEC.md) |
| **Master plan** | [MVP-PLAN.md](../MVP-PLAN.md) |

---

## Goal

Transform AI Protector from a **local-Ollama-only proxy** into a **universal LLM firewall**
that can protect traffic to **any commercial LLM provider** (OpenAI, Anthropic, Google, Mistral)
while keeping all security scanners running locally at zero cost.

After this step:
- Users paste their API key in the browser → stored in **SessionStorage** (never on server)
- Playground & Agent Demo can chat through GPT-4o, Claude, Gemini — all protected by the pipeline
- The proxy remains a **drop-in replacement**: clients change only `base_url` to get full protection
- API key lives exclusively in the user's browser — close tab = key gone

### Why This Matters

Today AI Protector works only with Ollama (local, slow on CPU). Real-world adoption requires:

```
┌──────────────────────────────────────────────────────┐
│  Client app (Java, Python, JS, curl...)              │
│  base_url = "https://ai-protector.company.com/v1"    │
│  model = "gpt-4o"  ← just change this string         │
└──────────────┬───────────────────────────────────────┘
               │  x-api-key: sk-proj-abc...
               ▼
┌──────────────────────────────────────────────────────┐
│  AI Protector Proxy :8000                            │
│  ┌─────────────────────────────────────────────────┐ │
│  │  NeMo Guardrails (7ms) │ Presidio │ LLM Guard  │ │
│  │  ← all local, free, fast                        │ │
│  └────────────────────┬────────────────────────────┘ │
│                       │ ALLOW                        │
│                       ▼                              │
│  ┌─────────────────────────────────────────────────┐ │
│  │  LiteLLM routing layer                          │ │
│  │  model "gpt-4o"     → api.openai.com   + key    │ │
│  │  model "gemini/..."  → googleapis.com  + key    │ │
│  │  model "anthropic/." → api.anthropic.com + key  │ │
│  │  model "ollama/..."  → localhost:11434 (no key) │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## Key Architecture Decision: SessionStorage (No Server Storage)

### Why **NOT** store API keys in the database?

| Concern | DB approach | SessionStorage approach |
|---------|-------------|------------------------|
| Data breach liability | Server holds encrypted keys — one breach = all keys | Server holds **nothing** — nothing to breach |
| Trust model | "Trust us with your keys" | Zero trust — key never leaves browser |
| Complexity | Fernet encryption, Alembic migrations, CRUD API, key rotation | Zero backend storage code |
| GDPR/compliance | API key = personal data → retention policies needed | Not applicable — server never sees storage |
| Market precedent | None of the major platforms do this | ✅ lmsys.org, Vercel AI Playground, Typingmind — all use browser storage |
| UX | Persistent (survives tab close) | SessionStorage: closes with tab (secure default). Optional: "Remember on this device" → localStorage |

**Decision**: API key stored in browser **SessionStorage** (default) with optional **localStorage** ("Remember" checkbox).
Backend reads key from `x-api-key` request header per-request. **Server never stores, logs, or caches the key.**

### API Key Flow

```
User pastes API key in browser:
  ┌──────────────────────────────────────────┐
  │  🔑 API Key Settings                     │
  │                                          │
  │  Provider: [▼ OpenAI          ]          │
  │  API Key:  [sk-proj-abc..._____]         │
  │  ☐ Remember on this device               │
  │                                          │
  │              [Save]  [Clear]             │
  └──────────────┬───────────────────────────┘
                 │
                 ▼
  sessionStorage.setItem("apiKey:openai", "sk-proj-abc...")
  // or localStorage if "Remember" checked
                 │
                 ▼
  Every chat request:
  fetch("/v1/chat/completions", {
    headers: {
      "x-api-key": sessionStorage.getItem("apiKey:openai"),
      "x-policy": "balanced",
    },
    body: { model: "gpt-4o", messages: [...] }
  })
                 │
                 ▼
  Backend reads header → passes to LiteLLM → discards immediately
  ⚠️ Key is NEVER stored, logged, or cached on the server
```

---

## Sub-steps

| # | File | Scope | Est. |
|---|------|-------|------|
| a | [23a — Backend Provider Routing](23a-provider-routing.md) | `detect_provider()`, `format_litellm_model()`, modify `llm_completion()` to read `api_key` from parameter, `GET /v1/models` endpoint | 3–4h |
| b | [23b — Frontend: API Key Settings & Model Selector](23b-frontend-settings.md) | API key dialog (SessionStorage/localStorage), model selector in Playground/Agent, `x-api-key` header injection | 3–4h |

---

## Provider Routing (in LLM client)

```python
# Current (hardcoded Ollama):
litellm_model = f"ollama/{model}"
api_base = settings.ollama_base_url

# After Step 23a:
provider = detect_provider(model)       # "gpt-4o" → "openai"
if provider == "ollama":
    litellm_model = f"ollama/{model}"
    kwargs = {"api_base": settings.ollama_base_url}
else:
    litellm_model = format_litellm_model(model, provider)
    api_key = api_key_from_header       # read from x-api-key header
    if not api_key:
        raise HTTPException(401, "API key required for external providers")
    kwargs = {"api_key": api_key}

response = await acompletion(model=litellm_model, messages=..., **kwargs)
```

## Provider Detection Rules

| Model pattern | Provider | LiteLLM model format |
|---------------|----------|---------------------|
| `gpt-*`, `o1-*`, `o3-*` | openai | `gpt-4o` (as-is) |
| `claude-*` | anthropic | `anthropic/claude-sonnet-4-6` |
| `gemini/*` | google | `gemini/gemini-2.5-flash` (as-is) |
| `mistral-*`, `codestral-*` | mistral | `mistral/mistral-large` |
| `ollama/*` | ollama | `ollama/llama3.1:8b` (as-is) |
| Other (no prefix match) | ollama | `ollama/{model}` (backward compatible) |

---

## Security Considerations

| Concern | Solution |
|---------|----------|
| API key storage | **Browser only** — SessionStorage (default) or localStorage (opt-in) |
| Key on server | **Never stored** — read from `x-api-key` header, passed to LiteLLM, discarded |
| Key in logs | Never logged — request logging excludes headers with keys |
| Key in transit | HTTPS in production; local dev is HTTP (acceptable) |
| Tab closed | SessionStorage auto-clears — key gone immediately |
| "Remember" opt-in | localStorage persists across sessions — user's explicit choice |
| Multiple providers | Separate keys per provider: `apiKey:openai`, `apiKey:anthropic`, etc. |

---

## Supported Providers

| Provider | Models (examples) | Needs `api_base`? | Notes |
|----------|------------------|-------------------|-------|
| **openai** | gpt-4o, gpt-4o-mini, o1, o3-mini | No | LiteLLM default |
| **anthropic** | claude-sonnet-4-6, claude-haiku-4-5 | No | Prefix `anthropic/` |
| **google** | gemini-2.5-flash, gemini-pro | No | Prefix `gemini/` |
| **mistral** | mistral-large, codestral | No | Prefix `mistral/` |
| **ollama** | llama3.1:8b, phi3:mini, etc. | Yes (local) | Always available, no key needed |
| **azure** | gpt-4 (Azure deployment) | Yes (custom) | Future — needs `api_base` + `api_version` |

---

## Tests

| Area | Tests |
|------|-------|
| Encryption | `encrypt_token()` ↔ `decrypt_token()` roundtrip, `mask_key()` format |
| Token CRUD | POST creates + returns masked, GET lists, DELETE removes, duplicate provider OK |
| Provider detection | `detect_provider("gpt-4o")` → openai, `detect_provider("ollama/llama3.1:8b")` → ollama |
| LLM routing | Mock LiteLLM: verify `api_key` passed for openai, `api_base` passed for ollama |
| No token error | Missing provider key → clear 422 error: "No API key found for provider 'openai'" |
| Frontend | Token form validation, masked display, delete confirmation |

---

## Definition of Done

- [ ] `ApiToken` model in DB with Fernet-encrypted `encrypted_key` column
- [ ] `POST /v1/tokens` encrypts and stores key, returns masked hint
- [ ] `GET /v1/tokens` returns list with `key_hint` only (never the secret)
- [ ] `DELETE /v1/tokens/{id}` hard-deletes the key
- [ ] `llm_completion()` auto-detects provider from model name
- [ ] `llm_completion()` fetches decrypted key from DB for non-Ollama providers
- [ ] Ollama remains the default (backward compatible, no key needed)
- [ ] Frontend "Tokens" page: add, list, delete API keys
- [ ] Playground model dropdown includes external models when tokens exist
- [ ] Agent Demo model dropdown includes external models when tokens exist
- [ ] All unit tests pass (encryption, CRUD, routing, detection)
- [ ] E2E: add OpenAI token → select gpt-4o in Playground → chat works through proxy with full scanning

---

| **Prev** | **Next** |
|---|---|
| [Step 22 — NeMo Guardrails](../22-nemo-guardrails/SPEC.md) | [Step 24 — Compare Playground](../24-compare-playground/SPEC.md) |
