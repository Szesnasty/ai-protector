# 08 — HTTP Client

> **Module:** `red-team/engine/http_client`
> **Phase:** 0 (Foundation) — MVP
> **Depends on:** Scenario Schema (`red-team/schemas/` — for `RawTargetResponse`, `ToolCall`)

## Scope

Sends attack prompts to the target endpoint and returns a raw HTTP response (`HttpResponse`). Handles auth headers, timeouts, and basic response capture. This is the only module that makes network calls.

> **Important boundary:** The HTTP Client returns a raw `HttpResponse`, NOT a `RawTargetResponse`. The Response Normalizer (`red-team/normalizer/`) sits between the HTTP Client and the Evaluator Engine, converting provider-specific formats into the canonical `RawTargetResponse`.

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

### Step 2: Define `HttpResponse` (raw output)

```python
@dataclass
class HttpResponse:
    status_code: int
    headers: dict[str, str]    # Lowercase keys
    body: str                  # Raw response body (text)
    latency_ms: float          # Round-trip time
```

> This is NOT `RawTargetResponse`. The Response Normalizer converts `HttpResponse` → `RawTargetResponse`.

### Step 3: Implement `send_prompt()`

```python
async def send_prompt(prompt: str, target: TargetEndpoint) → HttpResponse:
    """Send attack prompt to target, return raw HTTP response."""
```

- POST to `target.url` with body: `{"message": prompt}` (configurable field name)
- Add `Authorization` header if `auth_header` is set
- Measure latency (start → response received)
- Capture raw response: `status_code`, `headers` (lowercase), `body` (raw text), `latency_ms`
- No parsing, no tool call extraction — that's the normalizer's job

### Step 4: Error handling

- `TimeoutError` — raised when response exceeds `timeout_s`
- `ConnectionError` — raised when target unreachable
- Non-2xx status codes → still return `HttpResponse` (normalizer + evaluators decide pass/fail)
- SSL errors → raise `ConnectionError` with descriptive message

### Step 5: Request format configurability

- Default: `{"message": "{prompt}"}`
- Could support custom templates in future, but for MVP keep it simple
- Special handling for demo agent (known format)

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_send_prompt_success` | 200 response → correct `HttpResponse` |
| `test_send_prompt_with_auth` | Auth header included in request |
| `test_send_prompt_timeout` | Slow target → `TimeoutError` |
| `test_send_prompt_connection_error` | Unreachable target → `ConnectionError` |
| `test_body_is_raw_text` | Response body returned as raw string (no parsing) |
| `test_latency_measured` | `latency_ms` > 0 for any response |
| `test_non_2xx_still_returns_response` | 400/500 → `HttpResponse` with status_code |
| `test_headers_lowercase` | `Content-Type` → `content-type` in headers dict |
| `test_no_tool_call_extraction` | HTTP Client does NOT extract tool calls (normalizer's job) |

## Definition of Done

- [ ] `send_prompt()` sends attack prompt and returns raw `HttpResponse`
- [ ] Auth header handling (added when present, never logged)
- [ ] No JSON parsing, no tool call extraction (that's the normalizer's job)
- [ ] Latency measurement
- [ ] Proper error types for timeout and connection failures
- [ ] All tests pass with mock HTTP server (httpx mock or respx)
- [ ] No business logic — just HTTP + raw response capture
