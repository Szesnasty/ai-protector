# 09 — Response Normalizer

> **Module:** `red-team/normalizer/`
> **Phase:** 0 (Foundation) — MVP
> **Depends on:** Scenario Schema (`red-team/schemas/` — for `RawTargetResponse`, `ToolCall`), HTTP Client (`red-team/engine/http_client` — for `HttpResponse`)
> **Created:** 2026-03-24 — final source of truth for normalization contract

## Scope

Converts raw HTTP responses (provider-specific formats) into the canonical `RawTargetResponse` that evaluators consume. Pure function — no network calls, no persistence. This module sits between the HTTP Client and the Evaluator Engine.

```
HTTP Client → HttpResponse → Response Normalizer → RawTargetResponse → Evaluator Engine
```

---

## Input / Output Contracts

### Input: `HttpResponse` (from HTTP Client)

```python
@dataclass
class HttpResponse:
    status_code: int
    headers: dict[str, str]    # Lowercase keys
    body: str                  # Raw response body (text)
    latency_ms: float          # Round-trip time
```

### Output: `RawTargetResponse` (to Evaluator Engine)

```python
@dataclass
class RawTargetResponse:
    body_text: str                       # Extracted text content (always present, may be "")
    parsed_json: dict | None             # If response was JSON, parsed dict; else None
    tool_calls: list[ToolCall] | None    # Extracted tool calls (provider-independent); else None
    status_code: int                     # HTTP status code (passed through)
    latency_ms: float                    # Round-trip time (passed through)
    raw_body: str                        # Original response body (for debugging / logging)
    provider_format: str                 # Detected format: "openai" | "anthropic" | "generic_json" | "plain_text"

@dataclass
class ToolCall:
    name: str                            # Tool / function name
    arguments: dict                      # Parsed arguments
```

---

## Implementation Steps

### Step 1: Implement format detection strategy

```python
def detect_format(http_response: HttpResponse) → str:
    """Detect provider format from response structure."""
```

Detection order (first match wins):

1. **OpenAI**: JSON body contains `choices[].message` structure
2. **Anthropic**: JSON body contains `content[].type` structure
3. **Generic JSON**: Body is valid JSON but doesn't match known provider formats
4. **Plain text**: Body is not valid JSON
5. **Fallback**: If detection fails, treat as `plain_text`

Return value: `"openai"` | `"anthropic"` | `"generic_json"` | `"plain_text"`

### Step 2: Implement provider-specific extractors

#### OpenAI Extractor

```python
def extract_openai(parsed: dict) → tuple[str, list[ToolCall] | None]:
    """Extract text and tool calls from OpenAI format."""
```

- Text: `choices[0].message.content` (may be `None` if tool call only)
- Tool calls: `choices[0].message.tool_calls` → map to `ToolCall` objects
- Handle streaming chunks (combined) and non-streaming responses

#### Anthropic Extractor

```python
def extract_anthropic(parsed: dict) → tuple[str, list[ToolCall] | None]:
    """Extract text and tool calls from Anthropic format."""
```

- Text: Join `content[]` blocks where `type == "text"`, extract `.text`
- Tool calls: `content[]` blocks where `type == "tool_use"` → map to `ToolCall(name=block.name, arguments=block.input)`

#### Generic JSON Extractor

```python
def extract_generic_json(parsed: dict) → tuple[str, list[ToolCall] | None]:
    """Best-effort extraction from unknown JSON format."""
```

- Text: Try common field names: `message`, `text`, `response`, `content`, `output`, `answer`
- Tool calls: Try `tool_calls`, `function_calls`, `actions` — map to `ToolCall` if structure matches
- Fallback: `json.dumps(parsed)` as text, `None` for tool calls

#### Plain Text Extractor

```python
def extract_plain_text(body: str) → tuple[str, list[ToolCall] | None]:
    """Body is the text, no tool calls."""
```

- Text: `body.strip()`
- Tool calls: `None`

### Step 3: Implement main normalize function

```python
def normalize(http_response: HttpResponse) → RawTargetResponse:
    """Convert raw HTTP response to canonical RawTargetResponse."""
```

Pipeline:
1. Attempt JSON parse of `body`
2. If JSON: detect provider format, call appropriate extractor
3. If not JSON: use plain text extractor
4. Assemble `RawTargetResponse` with all fields populated
5. `raw_body` always set to original `body`
6. `body_text` always a string (never `None`)

### Step 4: Handle edge cases

- Empty body → `body_text = ""`, `parsed_json = None`, `tool_calls = None`
- JSON parse error → treat as plain text
- OpenAI with `choices = []` → `body_text = ""`, no crash
- Anthropic with no `content` blocks → `body_text = ""`
- Tool call with missing `arguments` → `arguments = {}`
- Non-UTF-8 responses → decode with `errors='replace'`

---

## Tests

| Test | What it verifies |
|------|-----------------|
| `test_detect_openai_format` | Response with `choices[].message` → `"openai"` |
| `test_detect_anthropic_format` | Response with `content[].type` → `"anthropic"` |
| `test_detect_generic_json` | Valid JSON without known structure → `"generic_json"` |
| `test_detect_plain_text` | Non-JSON body → `"plain_text"` |
| `test_normalize_openai_text_only` | OpenAI response with text → `body_text` populated |
| `test_normalize_openai_tool_calls` | OpenAI response with tool calls → `tool_calls` list |
| `test_normalize_openai_text_and_tools` | Both text and tool calls extracted |
| `test_normalize_anthropic_text` | Anthropic text blocks joined correctly |
| `test_normalize_anthropic_tool_use` | Anthropic tool_use blocks → `tool_calls` |
| `test_normalize_generic_json_message_field` | JSON with `message` field → `body_text` |
| `test_normalize_generic_json_fallback` | Unknown JSON → `json.dumps()` as text |
| `test_normalize_plain_text` | Raw text → `body_text = text`, `parsed_json = None` |
| `test_normalize_empty_body` | Empty string → `body_text = ""`, no crash |
| `test_normalize_preserves_raw_body` | `raw_body` always equals original body |
| `test_normalize_preserves_status_code` | Status code passed through from HttpResponse |
| `test_normalize_preserves_latency` | Latency passed through from HttpResponse |
| `test_body_text_never_none` | `body_text` is always a string, never `None` |
| `test_tool_call_missing_arguments` | Tool call with no args → `arguments = {}` |
| `test_non_utf8_handled` | Binary/malformed response decoded safely |
| `test_openai_empty_choices` | `choices = []` → `body_text = ""`, no crash |
| `test_provider_format_set` | `provider_format` always set to detected value |
| `test_normalize_is_pure_function` | No side effects, no network calls, idempotent |

## Definition of Done

- [ ] `normalize(HttpResponse) → RawTargetResponse` implemented
- [ ] Format detection works for OpenAI, Anthropic, generic JSON, plain text
- [ ] Text extraction works for all 4 formats
- [ ] Tool call extraction works for OpenAI and Anthropic formats
- [ ] `body_text` is always a string (never `None`)
- [ ] `raw_body` always preserves original response body
- [ ] `provider_format` always set to detected format
- [ ] All edge cases handled (empty body, parse errors, missing fields)
- [ ] All tests pass, >95% coverage (pure functions = easy to test)
- [ ] No I/O, no network calls, no imports outside `schemas/` and `http_client`
