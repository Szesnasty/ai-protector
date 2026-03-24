# 08 — HTTP Client

> **Module:** `red-team/engine/http_client`
> **Phase:** 0 (Foundation) — MVP
> **Depends on:** Scenario Schema (`red-team/schemas/` — for `RawTargetResponse`, `ToolCall`)

## Scope

Sends attack prompts to the target endpoint and returns a standardized `RawTargetResponse`. Handles auth headers, timeouts, and response parsing. This is the only module that makes network calls.

## Implementation Steps

### Step 1: Define target configuration

```python
@dataclass
class TargetEndpoint:
    url: str
    auth_header: str | None        # Decrypted at call time, never stored
    timeout_s: int = 30
    content_type: str = "application/json"
```

### Step 2: Implement `send_prompt()`

```python
async def send_prompt(prompt: str, target: TargetEndpoint) → RawTargetResponse:
    """Send attack prompt to target, return standardized response."""
```

- POST to `target.url` with body: `{"message": prompt}` (configurable field name)
- Add `Authorization` header if `auth_header` is set
- Measure latency (start → response received)
- Parse response into `RawTargetResponse`:
  - `status_code`, `headers` (lowercase keys)
  - `body_text` (raw text)
  - `parsed_json` (attempt parse, None on failure)
  - `tool_calls` (extract from response if present — see Step 3)
  - `latency_ms`

### Step 3: Implement tool call extraction

- Look for tool calls in common formats:
  - OpenAI format: `response.choices[0].message.tool_calls`
  - Generic: `response.tool_calls` or `response.function_calls`
  - Fallback: regex scan for function-call-like patterns in body_text
- Return `list[ToolCall]` or `None` if no tool calls found
- This is best-effort — external targets may not expose tool calls

### Step 4: Error handling

- `TimeoutError` — raised when response exceeds `timeout_s`
- `ConnectionError` — raised when target unreachable
- Non-2xx status codes → still return `RawTargetResponse` (evaluators decide pass/fail)
- SSL errors → raise `ConnectionError` with descriptive message

### Step 5: Request format configurability

- Default: `{"message": "{prompt}"}`
- Could support custom templates in future, but for MVP keep it simple
- Special handling for demo agent (known format)

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_send_prompt_success` | 200 response → correct `RawTargetResponse` |
| `test_send_prompt_with_auth` | Auth header included in request |
| `test_send_prompt_timeout` | Slow target → `TimeoutError` |
| `test_send_prompt_connection_error` | Unreachable target → `ConnectionError` |
| `test_parse_json_response` | JSON body → `parsed_json` populated |
| `test_parse_non_json_response` | HTML body → `parsed_json = None`, `body_text` populated |
| `test_extract_tool_calls_openai` | OpenAI format response → `tool_calls` list |
| `test_extract_tool_calls_none` | No tool calls → `tool_calls = None` |
| `test_latency_measured` | `latency_ms` > 0 for any response |
| `test_non_2xx_still_returns_response` | 400/500 → `RawTargetResponse` with status_code |
| `test_headers_lowercase` | `Content-Type` → `content-type` in headers dict |

## Definition of Done

- [ ] `send_prompt()` sends attack prompt and returns `RawTargetResponse`
- [ ] Auth header handling (added when present, never logged)
- [ ] JSON parsing with graceful fallback
- [ ] Tool call extraction (best-effort)
- [ ] Latency measurement
- [ ] Proper error types for timeout and connection failures
- [ ] All tests pass with mock HTTP server (httpx mock or respx)
- [ ] No business logic — just HTTP + response parsing
