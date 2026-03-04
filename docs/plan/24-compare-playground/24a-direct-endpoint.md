# Step 24a — Direct Bypass Endpoint

| | |
|---|---|
| **Parent** | [Step 24 — Compare Playground](SPEC.md) |
| **Estimated time** | 2–3 hours |
| **Produces** | `src/routers/chat_direct.py`, `src/llm/streaming.py` (sse_stream_direct) |

---

## Goal

Create a `POST /v1/chat/direct` endpoint that forwards requests **directly to the LLM**
without running any pipeline scanning, decision-making, or audit logging.
This exists purely for the Compare demo to show the difference between protected and
unprotected requests.

---

## Tasks

### 1. Config Flag

**File**: `src/config.py` — add:

```python
enable_direct_endpoint: bool = True  # Set False in production
```

### 2. Direct Chat Endpoint

**File**: `src/routers/chat_direct.py`

```python
@router.post("/v1/chat/direct")
async def chat_direct(body: ChatCompletionRequest, request: Request, ...):
    """Forward directly to LLM — NO scanning, NO policy, NO logging.
    
    For Compare demo only.
    """
    if not settings.enable_direct_endpoint:
        raise HTTPException(404, "Direct endpoint disabled")
    
    api_key = request.headers.get("x-api-key")  # From browser SessionStorage
    messages = [m.model_dump(exclude_none=True) for m in body.messages]
    
    if body.stream:
        llm_stream = await llm_completion(
            messages=messages, model=body.model,
            stream=True, temperature=body.temperature, max_tokens=body.max_tokens,
            api_key=api_key,  # Pass through — server never stores
        )
        return StreamingResponse(
            sse_stream_direct(llm_stream, request_id, body.model),
            media_type="text/event-stream",
            headers={"x-decision": "DIRECT"},
        )
    
    # Non-streaming
    response = await llm_completion(..., api_key=api_key)
    return ChatCompletionResponse(...)
```

**Key differences from `/v1/chat/completions`:**
- No `run_pipeline()` or `run_pre_llm_pipeline()` call
- No policy lookup
- No scanner execution
- No audit log to PostgreSQL/Langfuse
- Response header: `x-decision: DIRECT`

### 3. Simple SSE Streamer

**File**: `src/llm/streaming.py` — add `sse_stream_direct()`:

```python
async def sse_stream_direct(
    response: AsyncGenerator,
    request_id: str,
    model: str,
) -> AsyncGenerator[str, None]:
    """Minimal SSE streamer — no audit logging, no pipeline metadata."""
    async for chunk in response:
        # ... format SSE chunk (same as sse_stream but no _audit_log())
        yield f"data: {sse_chunk.model_dump_json()}\n\n"
    yield "data: [DONE]\n\n"
```

### 4. Register Router

**File**: `src/main.py`:

```python
from src.routers.chat_direct import router as chat_direct_router
app.include_router(chat_direct_router)
```

---

## Tests

| Test | Assertion |
|------|-----------|
| `test_direct_returns_response` | POST → 200, response has `choices[0].message.content` |
| `test_direct_no_scanner_headers` | Response headers have `x-decision: DIRECT`, no `x-risk-score` |
| `test_direct_no_audit_log` | No new row in `requests` table after direct call |
| `test_direct_streaming` | SSE stream yields tokens, ends with `[DONE]` |
| `test_direct_disabled` | `enable_direct_endpoint=False` → POST returns 404 |
| `test_direct_uses_provider_routing` | `model: "gpt-4o"` + `x-api-key` header → uses OpenAI (via Step 23a) |

---

## Definition of Done

- [ ] `src/routers/chat_direct.py` with `POST /v1/chat/direct`
- [ ] `sse_stream_direct()` in `src/llm/streaming.py` (no audit logging)
- [ ] `enable_direct_endpoint` config flag (default: True for dev)
- [ ] Router registered in `src/main.py`
- [ ] Endpoint uses provider routing from Step 23a (works with external models via `x-api-key` header)
- [ ] Response header `x-decision: DIRECT`
- [ ] No database writes (no audit log)
- [ ] All unit tests pass

---

| **Prev** | **Next** |
|---|---|
| [Step 24 — SPEC.md](SPEC.md) | [Step 24b — Compare UI](24b-compare-ui.md) |
