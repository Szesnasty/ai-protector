# 04c — Request Logger & Tests

| | |
|---|---|
| **Parent** | [Step 04 — Basic LLM Proxy](SPEC.md) |
| **Prev sub-step** | [04b — Chat Endpoint & Streaming](04b-chat-endpoint.md) |
| **Estimated time** | 1–2 hours |

---

## Goal

Implement fire-and-forget request logging to the database, write all unit and integration tests for Step 04, and verify end-to-end Docker operation.

---

## Tasks

### 1. Request logger service (`src/services/request_logger.py`)

- [ ] Create `src/services/` package with `__init__.py`
- [ ] Implement async logging function:
  ```python
  async def log_request(
      client_id: str | None,
      policy_name: str,
      model: str,
      messages: list[dict],
      decision: str,       # "ALLOW" for now (no pipeline yet)
      latency_ms: int,
      tokens_in: int | None,
      tokens_out: int | None,
  ) -> None:
      """Write request to DB. Non-blocking — errors logged, not raised."""
  ```
- [ ] Compute `prompt_hash` — SHA-256 of last user message
- [ ] Compute `prompt_preview` — first 200 chars of last user message
- [ ] Lookup `policy_id` by name (cache lookup via dict or `lru_cache`)
- [ ] Insert into `requests` table:
  - `decision = "ALLOW"` (always in this step — pipeline not yet wired)
  - `intent = None` (not yet classified)
  - `risk_flags = {}`, `risk_score = 0.0`
- [ ] Wrap in `try/except` — never let logging failure break the proxy response
- [ ] Log errors via structlog

### 2. Wire logger into chat router

- [ ] After LLM response (non-streaming), call `log_request()`:
  ```python
  # Fire-and-forget via asyncio.create_task
  asyncio.create_task(log_request(
      client_id=client_id,
      policy_name=policy,
      model=request.model,
      messages=[m.model_dump() for m in request.messages],
      decision="ALLOW",
      latency_ms=int(elapsed_ms),
      tokens_in=usage.prompt_tokens if usage else None,
      tokens_out=usage.completion_tokens if usage else None,
  ))
  ```
- [ ] After streaming completes, fire logging task with accumulated token counts

### 3. Schema tests (`tests/test_chat_schemas.py`)

- [ ] Validate `ChatCompletionRequest` with minimal input (model + messages)
- [ ] Validate `ChatCompletionRequest` with all optional fields
- [ ] Reject empty `messages` list
- [ ] Reject `temperature` out of range (< 0 or > 2)
- [ ] Validate `ChatCompletionResponse` round-trip

### 4. Endpoint tests (`tests/test_chat_endpoint.py`)

- [ ] Mock `litellm.acompletion` → test non-streaming response shape
- [ ] Mock `litellm.acompletion(stream=True)` → test SSE response format
  - Verify `data: {...}\n\n` format
  - Verify `data: [DONE]\n\n` at end
- [ ] Test error case: Ollama down → 502 response
- [ ] Test `x-correlation-id` header present in response
- [ ] Test `x-client-id` and `x-policy` headers are accepted

### 5. Request logger tests (`tests/test_request_logger.py`)

- [ ] Mock DB session → verify `Request` model insert with correct fields
- [ ] Verify `prompt_hash` is valid SHA-256 hex (64 chars)
- [ ] Verify `prompt_preview` is truncated to 200 chars
- [ ] Verify logging failure doesn't raise (mock session.commit() to throw)

### 6. Docker / Compose verification

- [ ] Ensure `ollama` service is reachable from `proxy-service` container
- [ ] Pull model inside Ollama container:
  ```bash
  docker compose exec ollama ollama pull llama3.1:8b
  ```
- [ ] Test end-to-end (non-streaming):
  ```bash
  curl -s http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"Say hello"}]}' | python3 -m json.tool
  ```
- [ ] Test end-to-end (streaming):
  ```bash
  curl -N http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"Say hello"}],"stream":true}'
  ```
- [ ] Verify request logged in DB:
  ```bash
  docker compose exec -T db psql -U postgres -d ai_protector \
    -c "SELECT decision, prompt_preview, latency_ms FROM requests ORDER BY created_at DESC LIMIT 3;"
  ```

---

## Definition of Done

- [ ] `src/services/request_logger.py` exists with `log_request()` function
- [ ] Every chat request creates a row in `requests` table
- [ ] `prompt_hash` = SHA-256, `prompt_preview` = first 200 chars
- [ ] Logger failure does NOT break the proxy response
- [ ] `pytest tests/test_chat_schemas.py` → all pass
- [ ] `pytest tests/test_chat_endpoint.py` → all pass (mocked LLM)
- [ ] `pytest tests/test_request_logger.py` → all pass (mocked DB)
- [ ] `ruff check src/ tests/` → 0 errors
- [ ] End-to-end: `curl` from host → proxy → Ollama → response (non-streaming + streaming)
- [ ] Docker: `proxy-service` container successfully proxies to `ollama` container
- [ ] DB: `SELECT * FROM requests` shows logged requests

---

| **Prev** | **Parent** |
|---|---|
| [04b — Chat Endpoint & Streaming](04b-chat-endpoint.md) | [Step 04 — SPEC](SPEC.md) |
