# Step 23a — Backend Provider Routing

| | |
|---|---|
| **Parent** | [Step 23 — External LLM Providers](SPEC.md) |
| **Estimated time** | 3–4 hours |
| **Produces** | `src/llm/providers.py`, modified `src/llm/client.py`, `GET /v1/models` endpoint |

---

## Goal

Modify the LLM client so that `llm_completion()` can route to **any provider**
based on the model name. The API key comes from the request's `x-api-key` header —
**the server never stores it**. Also expose a `GET /v1/models` endpoint returning
all known model options (static catalog + live Ollama tags).

---

## Tasks

### 1. Provider Detection

**File**: `src/llm/providers.py`

```python
"""Provider detection and routing for LiteLLM."""

# Pattern → Provider mapping (order matters: first match wins)
PROVIDER_RULES: list[tuple[str, str]] = [
    # Explicit prefixes (user-provided)
    ("ollama/", "ollama"),
    ("anthropic/", "anthropic"),
    ("gemini/", "google"),
    ("mistral/", "mistral"),
    ("azure/", "azure"),
    # Model name patterns (no prefix needed)
    ("gpt-", "openai"),
    ("o1", "openai"),
    ("o3", "openai"),
    ("claude-", "anthropic"),
    ("mistral-", "mistral"),
    ("codestral", "mistral"),
]

def detect_provider(model: str) -> str:
    """Detect LLM provider from model name.
    
    Returns "ollama" as default for unrecognized models (backward compatible).
    """
    model_lower = model.lower()
    for pattern, provider in PROVIDER_RULES:
        if model_lower.startswith(pattern):
            return provider
    return "ollama"


def format_litellm_model(model: str, provider: str) -> str:
    """Format model name for LiteLLM.
    
    LiteLLM expects certain prefixes:
    - OpenAI: "gpt-4o" (as-is, no prefix)
    - Anthropic: "anthropic/claude-3.5-sonnet" (needs prefix if not present)
    - Google: "gemini/gemini-2.5-flash" (as-is if prefixed)
    - Ollama: "ollama/llama3.1:8b" (needs prefix if not present)
    """
    if provider == "ollama" and not model.startswith("ollama/"):
        return f"ollama/{model}"
    if provider == "anthropic" and not model.startswith("anthropic/"):
        return f"anthropic/{model}"
    if provider == "google" and not model.startswith("gemini/"):
        return f"gemini/{model}"
    if provider == "mistral" and not model.startswith("mistral/"):
        return f"mistral/{model}"
    # OpenAI: no prefix needed
    return model
```

### 2. Modify `llm_completion()`

**File**: `src/llm/client.py`

Add an `api_key: str | None = None` parameter. Provider detection replaces the hardcoded
Ollama routing.

```python
from src.llm.providers import detect_provider, format_litellm_model

async def llm_completion(
    messages: list[dict],
    model: str = ...,
    stream: bool = True,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    api_key: str | None = None,        # ← NEW: from x-api-key header
) -> ...:
    provider = detect_provider(model)
    litellm_model = format_litellm_model(model, provider)

    kwargs: dict[str, Any] = {}
    if provider == "ollama":
        kwargs["api_base"] = settings.ollama_base_url
    else:
        if not api_key:
            raise LLMError(
                f"API key required for provider '{provider}'. "
                f"Add your key in Settings → API Keys.",
                status_code=401,
            )
        kwargs["api_key"] = api_key

    response = await acompletion(
        model=litellm_model,
        messages=messages,
        stream=stream,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=settings.request_timeout,
        **kwargs,
    )
    return response
```

**Key design decisions:**
- `api_key` parameter is optional — Ollama calls don't need it
- 401 error with helpful message if external provider lacks key
- No DB lookup, no decryption, no caching — key comes from the caller
- Backward compatible: existing Ollama calls work unchanged

### 3. Pass `api_key` Through the Pipeline

The chat completions router extracts `x-api-key` from the request header and passes it
down through the pipeline to `llm_completion()`.

**File**: `src/routers/chat.py` (or wherever the chat endpoint lives)

```python
@router.post("/v1/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    ...
):
    api_key = request.headers.get("x-api-key")  # None for Ollama
    # ... pass api_key down to pipeline / llm_completion()
```

The pipeline state/context needs to carry `api_key` so it reaches the LLM call node.

### 4. Available Models Endpoint

**File**: `src/routers/models.py`

```python
@router.get("/v1/models")
async def list_models() -> ModelsResponse:
    """Return catalog of available models.
    
    Static catalog of well-known external models
    + dynamic Ollama models (from Ollama API /api/tags).
    External models always listed — frontend knows which
    providers have a key via SessionStorage locally.
    """
```

**Response:**
```json
{
  "models": [
    { "id": "gpt-4o",            "provider": "openai",    "name": "GPT-4o" },
    { "id": "gpt-4o-mini",       "provider": "openai",    "name": "GPT-4o Mini" },
    { "id": "o3-mini",           "provider": "openai",    "name": "o3-mini" },
    { "id": "claude-3.5-sonnet", "provider": "anthropic", "name": "Claude 3.5 Sonnet" },
    { "id": "claude-3-haiku",    "provider": "anthropic", "name": "Claude 3 Haiku" },
    { "id": "gemini-2.5-flash",  "provider": "google",    "name": "Gemini 2.5 Flash" },
    { "id": "gemini-2.0-flash",  "provider": "google",    "name": "Gemini 2.0 Flash" },
    { "id": "mistral-large",     "provider": "mistral",   "name": "Mistral Large" },
    { "id": "codestral",         "provider": "mistral",   "name": "Codestral" },
    { "id": "ollama/llama3.1:8b","provider": "ollama",    "name": "Llama 3.1 8B" }
  ]
}
```

**Logic:**
- Static list of well-known external models (hardcoded — always returned)
- Ollama models queried from `GET http://ollama:11434/api/tags` (dynamic, with fallback)
- **No token check** — the frontend knows which providers have keys (it owns the keys)
- Frontend grays out models for providers without a stored key

### 5. Pydantic Schemas

**File**: `src/schemas/models.py`

```python
class ModelInfo(BaseModel):
    id: str          # "gpt-4o" or "ollama/llama3.1:8b"
    provider: str    # "openai", "anthropic", "google", "mistral", "ollama"
    name: str        # Human-readable: "GPT-4o", "Llama 3.1 8B"

class ModelsResponse(BaseModel):
    models: list[ModelInfo]
```

### 6. Register Router

**File**: `src/main.py`:

```python
from src.routers.models import router as models_router
app.include_router(models_router)
```

---

## Tests

| Test | Assertion |
|------|-----------|
| `test_detect_provider_openai` | `detect_provider("gpt-4o")` → `"openai"` |
| `test_detect_provider_anthropic_prefixed` | `detect_provider("anthropic/claude-3.5-sonnet")` → `"anthropic"` |
| `test_detect_provider_anthropic_bare` | `detect_provider("claude-3.5-sonnet")` → `"anthropic"` |
| `test_detect_provider_google` | `detect_provider("gemini/gemini-2.5-flash")` → `"google"` |
| `test_detect_provider_ollama_explicit` | `detect_provider("ollama/llama3.1:8b")` → `"ollama"` |
| `test_detect_provider_unknown_defaults_ollama` | `detect_provider("my-custom-model")` → `"ollama"` |
| `test_format_litellm_openai` | `format_litellm_model("gpt-4o", "openai")` → `"gpt-4o"` |
| `test_format_litellm_ollama` | `format_litellm_model("llama3.1:8b", "ollama")` → `"ollama/llama3.1:8b"` |
| `test_format_litellm_anthropic` | `format_litellm_model("claude-3.5-sonnet", "anthropic")` → `"anthropic/claude-3.5-sonnet"` |
| `test_llm_completion_ollama_no_key` | Mock acompletion: `api_base` passed, no `api_key` |
| `test_llm_completion_openai_with_key` | Mock acompletion: `api_key` passed, no `api_base` |
| `test_llm_completion_external_no_key_401` | No `api_key` + model "gpt-4o" → `LLMError(401)` |
| `test_llm_completion_backward_compatible` | Default model → still routes to Ollama, no key needed |
| `test_models_endpoint_returns_catalog` | `GET /v1/models` → 200, has openai + ollama models |
| `test_models_endpoint_includes_ollama_dynamic` | Mocked Ollama tags → dynamic models appear |
| `test_chat_passes_api_key_header` | `x-api-key` header → reaches `llm_completion(api_key=...)` |

---

## Definition of Done

- [ ] `src/llm/providers.py` with `detect_provider()` and `format_litellm_model()`
- [ ] `llm_completion()` accepts `api_key` parameter, routes to correct provider
- [ ] Chat endpoint extracts `x-api-key` from header and passes down the pipeline
- [ ] 401 error with clear message when external model called without key
- [ ] `GET /v1/models` returns static catalog + dynamic Ollama models
- [ ] Router registered in `src/main.py`
- [ ] Backward compatible — Ollama calls need zero changes
- [ ] **Server never stores, logs, or caches API keys**
- [ ] All unit tests pass

---

| **Prev** | **Next** |
|---|---|
| [Step 23 — SPEC.md](SPEC.md) | [Step 23b — Frontend Settings](23b-frontend-settings.md) |
