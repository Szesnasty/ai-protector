# 04b — Chat Endpoint & Streaming

| | |
|---|---|
| **Parent** | [Step 04 — Basic LLM Proxy](SPEC.md) |
| **Prev sub-step** | [04a — LiteLLM Client & Schemas](04a-litellm-schemas.md) |
| **Next sub-step** | [04c — Request Logger & Tests](04c-logging-tests.md) |
| **Estimated time** | 1.5–2 hours |

---

## Goal

Create the `POST /v1/chat/completions` router with both non-streaming and SSE streaming modes, plus the SSE helper and structured error handling.

---

## Tasks

### 1. Chat completions router (`src/routers/chat.py`)

- [x] Create the main endpoint:
  ```
  POST /v1/chat/completions
  Headers:
    Authorization: Bearer <token>   (optional, pass-through — no auth in MVP)
    x-client-id: <string>           (optional, for request logging)
    x-policy: <string>              (optional, default from Settings.default_policy)
  Body: ChatCompletionRequest
  ```
- [x] **Non-streaming flow** (`stream: false`):
  1. Validate request body
  2. Call `llm_completion()` with `stream=False`
  3. Transform LiteLLM response → `ChatCompletionResponse`
  4. Log request metadata with structlog (model, tokens, latency)
  5. Return JSON response
- [x] **Streaming flow** (`stream: true`):
  1. Validate request body
  2. Return `StreamingResponse(media_type="text/event-stream")`
  3. Generator yields: `data: {json_chunk}\n\n` per token
  4. Final yield: `data: [DONE]\n\n`
  5. Log aggregate metadata after stream completes
- [x] Measure end-to-end latency (`time.perf_counter()`) and log it
- [x] Read `x-client-id` and `x-policy` headers via FastAPI `Header()` dependency

### 2. SSE streaming helper (`src/llm/streaming.py`)

- [x] Create SSE generator:
  ```python
  async def sse_stream(
      response: AsyncGenerator,
      request_id: str,
      model: str,
  ) -> AsyncGenerator[str, None]:
      """
      Converts LiteLLM streaming response to SSE-formatted chunks.
      Yields: "data: {json}\n\n"
      Final: "data: [DONE]\n\n"
      """
      created = int(time.time())
      async for chunk in response:
          delta = chunk.choices[0].delta
          sse_chunk = ChatCompletionChunk(
              id=request_id,
              created=created,
              model=model,
              choices=[ChatCompletionChunkChoice(
                  index=0,
                  delta=ChatCompletionChunkDelta(
                      role=getattr(delta, "role", None),
                      content=getattr(delta, "content", None),
                  ),
                  finish_reason=getattr(chunk.choices[0], "finish_reason", None),
              )],
          )
          yield f"data: {sse_chunk.model_dump_json()}\n\n"
      yield "data: [DONE]\n\n"
  ```
- [x] Track token count during streaming (accumulate from chunks or count post-hoc)

### 3. Error handling

- [x] Map exceptions to HTTP status codes:
  | Exception | Status | Error type |
  |-----------|--------|------------|
  | `ChatCompletionRequest` validation | 422 | `invalid_request_error` |
  | `LLMUpstreamError` (Ollama down) | 502 | `upstream_error` |
  | `LLMModelNotFoundError` | 404 | `model_not_found` |
  | `LLMTimeoutError` | 504 | `timeout_error` |
  | `LLMError` (generic) | 500 | `internal_error` |
- [x] Use FastAPI exception handler or try/except in router
- [x] Include `x-correlation-id` in error responses (already set by middleware)
- [x] Return `ErrorResponse` schema on all errors

### 4. Wire into FastAPI app (`src/main.py`)

- [x] Register the chat router:
  ```python
  from src.routers.chat import router as chat_router
  app.include_router(chat_router)
  ```
- [x] Set LiteLLM log level in lifespan startup:
  ```python
  import os
  os.environ["LITELLM_LOG"] = settings.litellm_log_level
  ```

---

## Definition of Done

- [x] `POST /v1/chat/completions` with `stream: false` → returns OpenAI-compatible JSON
- [x] `POST /v1/chat/completions` with `stream: true` → returns SSE stream (`data: {chunk}\n\n` … `data: [DONE]\n\n`)
- [x] Response includes `usage` (prompt_tokens, completion_tokens, total_tokens) for non-streaming
- [x] Ollama down → HTTP 502 with `ErrorResponse`
- [x] Invalid model → HTTP 404 with `ErrorResponse`
- [x] `x-client-id` and `x-policy` headers read and available for logging
- [x] Router registered in `main.py`
- [x] `ruff check src/` → 0 errors

---

| **Prev** | **Next** |
|---|---|
| [04a — LiteLLM Client & Schemas](04a-litellm-schemas.md) | [04c — Request Logger & Tests](04c-logging-tests.md) |
