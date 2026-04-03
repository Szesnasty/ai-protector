# Step 04 — Basic LLM Proxy

| | |
|---|---|
| **Phase** | Foundation |
| **Estimated time** | 4–6 hours |
| **Prev** | [Step 03 — Proxy Service Foundation](../03-proxy-foundation/SPEC.md) |
| **Next** | [Step 06 — Pipeline Core (LangGraph)](../06-pipeline-core/SPEC.md) |
| **Master plan** | [MVP-PLAN.md](../MVP-PLAN.md) |

---

## Goal

Implement the `POST /v1/chat/completions` endpoint that proxies requests through to Ollama via **LiteLLM**.
The endpoint must be **OpenAI-compatible** (same request/response shape) and support **Server-Sent Events (SSE) streaming**.
No firewall logic yet — this is a clean passthrough that later steps will wrap with the security pipeline.

---

## Sub-steps

| # | File | Scope | Est. |
|---|------|-------|------|
| a | [04a — LiteLLM Client & Schemas](04a-litellm-schemas.md) | LiteLLM wrapper, OpenAI-compatible Pydantic models, config updates | 1–2h |
| b | [04b — Chat Endpoint & Streaming](04b-chat-endpoint.md) | `POST /v1/chat/completions` router, SSE streaming, error handling | 1.5–2h |
| c | [04c — Request Logger & Tests](04c-logging-tests.md) | Fire-and-forget DB logger, unit+integration tests, Docker verification | 1–2h |

---

## Architecture Overview

```
Client (curl / frontend / agent)
  │
  │  POST /v1/chat/completions
  │  Headers: x-client-id, x-policy
  │  Body: { model, messages, stream, temperature }
  │
  ▼
┌────────────────────────────────┐
│  Proxy Service (FastAPI)       │
│                                │
│  1. Validate request           │
│  2. Call Ollama via LiteLLM    │
│  3. Log to DB (fire & forget)  │
│  4. Return response / stream   │
└───────────────┬────────────────┘
                │
                ▼
         ┌─────────────┐
         │   Ollama     │
         │  (LLM)      │
         └─────────────┘
```

---

## Technical Decisions

### Why LiteLLM (not raw httpx to Ollama)?
LiteLLM provides a unified interface across 100+ LLM providers. Today we use Ollama. Tomorrow we can swap to OpenAI, Anthropic, or Azure with zero code changes — just change the model string. It also normalizes the response format and handles streaming chunks consistently.

### Why `x-policy` header (not body field)?
Policy selection is a transport concern, not a model parameter. Headers keep the body clean and OpenAI-compatible. The frontend or agent sets the policy via header; the proxy applies it.

### Why fire-and-forget logging?
Logging must never slow down or break the proxy response. If the DB is temporarily down, the LLM response should still reach the user. We log the error and move on.

---

## Definition of Done (aggregate)

All sub-step DoDs must pass. Quick smoke test:

```bash
# Non-streaming
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}]}' | python3 -m json.tool

# Streaming
curl -N http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}],"stream":true}'

# DB check
psql -U postgres -d ai_protector -c "SELECT decision, prompt_preview, latency_ms FROM requests ORDER BY created_at DESC LIMIT 3;"
```

---

| **Prev** | **Next** |
|---|---|
| [Step 03 — Proxy Service Foundation](../03-proxy-foundation/SPEC.md) | [Step 06 — Pipeline Core](../06-pipeline-core/SPEC.md) |
