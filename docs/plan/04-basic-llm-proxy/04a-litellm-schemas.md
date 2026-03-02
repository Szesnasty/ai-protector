# 04a — LiteLLM Client & Schemas

| | |
|---|---|
| **Parent** | [Step 04 — Basic LLM Proxy](SPEC.md) |
| **Next sub-step** | [04b — Chat Endpoint & Streaming](04b-chat-endpoint.md) |
| **Estimated time** | 1–2 hours |

---

## Goal

Create the LiteLLM client wrapper and all OpenAI-compatible Pydantic request/response schemas needed by the chat endpoint.

---

## Tasks

### 1. LiteLLM client wrapper (`src/llm/client.py`)

- [x] Create `src/llm/` package with `__init__.py`
- [x] Implement async LiteLLM wrapper:
  ```python
  from litellm import acompletion

  async def llm_completion(
      messages: list[dict],
      model: str,
      stream: bool = False,
      temperature: float = 0.7,
      max_tokens: int | None = None,
  ) -> dict | AsyncGenerator:
      """
      Calls Ollama via LiteLLM.
      model format for LiteLLM: "ollama/llama3.1:8b"
      """
      response = await acompletion(
          model=f"ollama/{model}",
          messages=messages,
          stream=stream,
          temperature=temperature,
          max_tokens=max_tokens,
          api_base=settings.ollama_base_url,
      )
      return response
  ```
- [x] Handle LiteLLM exceptions → map to custom exception classes:
  | LiteLLM error | Custom exception | HTTP mapping |
  |---------------|-----------------||--------------|
  | `ServiceUnavailableError` | `LLMUpstreamError` | 502 |
  | `NotFoundError` | `LLMModelNotFoundError` | 404 |
  | `Timeout` | `LLMTimeoutError` | 504 |
  | Generic | `LLMError` | 500 |
- [x] Add `LITELLM_LOG` env var config (set `"ERROR"` by default to silence verbose logs)

### 2. Chat schemas (`src/schemas/chat.py`)

- [x] **Request model**:
  ```python
  class ChatMessage(BaseModel):
      role: Literal["system", "user", "assistant", "tool"]
      content: str
      name: str | None = None

  class ChatCompletionRequest(BaseModel):
      model: str = "llama3.1:8b"
      messages: list[ChatMessage]
      temperature: float = Field(default=0.7, ge=0.0, le=2.0)
      max_tokens: int | None = Field(default=None, ge=1, le=32768)
      stream: bool = False
      # Pass-through fields (accepted but not used yet)
      top_p: float | None = None
      frequency_penalty: float | None = None
      presence_penalty: float | None = None
  ```
- [x] **Response models** (non-streaming):
  ```python
  class ChatChoice(BaseModel):
      index: int
      message: ChatMessage
      finish_reason: str | None = "stop"

  class Usage(BaseModel):
      prompt_tokens: int
      completion_tokens: int
      total_tokens: int

  class ChatCompletionResponse(BaseModel):
      id: str
      object: str = "chat.completion"
      created: int
      model: str
      choices: list[ChatChoice]
      usage: Usage | None = None
  ```
- [x] **Streaming chunk models**:
  ```python
  class ChatCompletionChunkDelta(BaseModel):
      role: str | None = None
      content: str | None = None

  class ChatCompletionChunkChoice(BaseModel):
      index: int
      delta: ChatCompletionChunkDelta
      finish_reason: str | None = None

  class ChatCompletionChunk(BaseModel):
      id: str
      object: str = "chat.completion.chunk"
      created: int
      model: str
      choices: list[ChatCompletionChunkChoice]
  ```
- [x] **Error response model**:
  ```python
  class ErrorDetail(BaseModel):
      message: str
      type: str
      code: str

  class ErrorResponse(BaseModel):
      error: ErrorDetail
  ```
- [x] Validation: `messages` must be non-empty, at least one `user` message required

### 3. Configuration updates (`src/config.py`)

- [x] Add new settings fields:
  ```python
  default_temperature: float = 0.7
  default_max_tokens: int = 4096
  litellm_log_level: str = "ERROR"
  request_timeout: int = 120   # seconds — max wait for LLM response
  ```

---

## Definition of Done

- [x] `src/llm/client.py` exists with `llm_completion()` async function
- [x] `src/llm/__init__.py` exports `llm_completion`
- [x] LiteLLM exceptions mapped to custom exception classes
- [x] `src/schemas/chat.py` has all 8 Pydantic models (request + response + streaming + error)
- [x] `ChatCompletionRequest` rejects empty `messages`, out-of-range `temperature`
- [x] Config updated with `litellm_log_level`, `request_timeout`, `default_temperature`, `default_max_tokens`
- [x] `ruff check src/` → 0 errors

---

| **Parent** | **Next** |
|---|---|
| [Step 04 — SPEC](SPEC.md) | [04b — Chat Endpoint & Streaming](04b-chat-endpoint.md) |
