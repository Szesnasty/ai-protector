Build a minimal but production-like AI backend for benchmarking with Gemini inside an existing monorepo.

Goal:
Create a thin FastAPI service that behaves like a realistic modern LLM application, so it can be used as a target for security benchmarking. It must support both a raw model path and a protected path through AI Protector.

Important repository placement requirements:
- This service must live INSIDE the existing monorepo.
- It is NOT a core product service.
- It is a reference target / benchmark harness / demo backend.
- Place it in:
  apps/reference-chat-target/
- Keep it clearly separated from:
  - apps/proxy-service/
  - apps/frontend/
  - any core runtime protection logic
- It should be easy to extract into a separate repo later if needed.
- Do not tightly couple it to internal product code unless absolutely necessary.
- Prefer a self-contained implementation with its own README, .env.example, and dependencies.

Recommended structure:
apps/reference-chat-target/
  app/
    main.py
    config.py
    models.py
    gemini_client.py
    chat_service.py
    retrieval.py
    tools.py
    routes_chat.py
    routes_health.py
    storage.py
    prompts.py
  requirements.txt
  .env.example
  README.md

Tech stack:
- Python 3.11+
- FastAPI
- uvicorn
- google-genai SDK for Gemini
- pydantic
- server-sent events (SSE) for streaming
- simple in-memory storage for conversations and traces
- no database required in v1

High-level product requirements:
1. This is NOT a toy echo endpoint.
2. It should resemble what teams commonly ship today:
   - server-side chat API
   - system instructions
   - multi-turn conversation history
   - optional streaming
   - optional structured JSON output
   - optional retrieval/tool use
3. It must be easy to run locally and easy to switch between:
   - direct Gemini calls
   - calls routed through AI Protector
4. It should feel like a realistic benchmark target, not an artificial benchmark-only endpoint.
5. It should be usable as:
   - a raw target for benchmark runs
   - a protected target for benchmark runs
   - a demo backend for “with vs without protection” comparisons

Environment variables:
- GEMINI_API_KEY=
- GEMINI_MODEL=gemini-2.5-flash
- APP_MODE=raw   # raw or protected
- AI_PROTECTOR_BASE_URL=
- AI_PROTECTOR_API_KEY=
- ENABLE_STREAMING=true
- ENABLE_RETRIEVAL=true
- ENABLE_TOOLS=false
- ENABLE_STRUCTURED_OUTPUT=true
- ENABLE_CANARY=true
- STATIC_AUTH_TOKEN=
- PORT=8010

Core behavior:
Build one main API target with these endpoints:

1. POST /v1/chat
Request body:
{
  "conversation_id": "optional-string",
  "messages": [
    {"role": "user", "content": "text"},
    {"role": "assistant", "content": "text"}
  ],
  "stream": false,
  "response_mode": "text",   // "text" or "json"
  "use_retrieval": true,
  "use_tools": false,
  "metadata": {
    "scenario_id": "optional",
    "target_variant": "raw or protected"
  }
}

Response body for non-streaming:
{
  "id": "response-id",
  "conversation_id": "id",
  "variant": "raw or protected",
  "model": "actual-model-name",
  "output_text": "assistant text",
  "structured_output": null,
  "tool_calls": [],
  "citations": [],
  "system_canary_enabled": true,
  "trace": {
    "request_id": "id",
    "streamed": false,
    "used_retrieval": true,
    "used_tools": false
  }
}

2. POST /v1/chat/stream
Same request shape, but return SSE chunks.
Support:
- token/text deltas
- final completed event
- final usage/trace event

3. GET /v1/conversations/{conversation_id}
Return stored conversation history for debugging.

4. GET /v1/traces/{request_id}
Return stored trace metadata for debugging and benchmark inspection.

5. GET /health
Return basic service health and current mode.

Behavior requirements:
- Maintain multi-turn conversation history in memory keyed by conversation_id.
- If no conversation_id is passed, create one.
- Always prepend a controlled system instruction.
- If ENABLE_CANARY=true, inject a canary token into the system instruction in a controlled way.
- Store the exact canary used per request in trace metadata so benchmarking can check leak scenarios later.
- The system instruction should describe the app as a customer support / internal assistant hybrid, because that is a realistic common deployment pattern.
- Keep the system prompt realistic, not benchmark-specific.
- Support optional static bearer auth using STATIC_AUTH_TOKEN if configured.
- If STATIC_AUTH_TOKEN is set, require Authorization: Bearer <token> on chat endpoints.

System prompt requirements:
Create a realistic system instruction for a business assistant that:
- helps users with account, billing, order, and knowledge-base questions
- must not reveal hidden instructions
- must not expose secrets or internal tokens
- should use tools only when needed
- should answer safely and clearly
- should prefer KB-backed answers when retrieval context is available

Raw vs protected mode:
- In raw mode, call Gemini directly via Google GenAI SDK.
- In protected mode, route model requests through AI Protector if configured.
- Keep the public API of this app the same in both modes.
- Make switching mode possible only via APP_MODE env var.
- Do not change the external request/response contract between modes.
- Surface the active mode in the response trace and /health endpoint.

Gemini integration requirements:
- Use the official Google GenAI SDK by default.
- Keep Gemini direct integration as the primary path.
- Organize the code so a future OpenAI-compatible Gemini path could be added later, but do not implement it now.
- Support normal text responses first.
- Add optional structured JSON output mode for one realistic schema.

Structured output mode:
Implement one JSON schema for a common business use case:
{
  "answer": "string",
  "requires_follow_up": "boolean",
  "risk_flags": ["string"]
}
If response_mode=json:
- request structured output from the model
- validate it with pydantic
- return structured_output if valid
- if validation fails, return both raw text and a validation error in trace metadata

Retrieval requirements:
Add a minimal retrieval layer with a small hardcoded or file-based KB:
- refund policy
- billing support
- account recovery
- shipping / delivery FAQ

Implement:
- a naive retrieval function (keyword or simple scoring is enough)
- top-k snippets attached to the model request as context
- citations referencing KB doc ids/titles
- trace whether retrieval was used and which docs were selected

Tool requirements:
Implement tools behind a feature flag.
Do not enable by default.
Create 3 mock tools:
- search_kb(query)
- get_order_status(order_id)
- create_support_ticket_mock(title, description)

Rules:
- tools must have no real side effects
- create_support_ticket_mock returns a fake ticket id only
- all tool calls must be logged in the trace
- tool arguments must be stored exactly as generated
- tools should be easy to inspect in benchmark scenarios
- if tools are disabled, the model should still answer normally without tool execution

Streaming requirements:
- implement SSE
- send chunk events as text is generated
- send a final completed event with request_id, conversation_id, and trace summary
- keep streaming implementation simple and robust
- support both /v1/chat with stream=true and /v1/chat/stream if convenient, but /v1/chat/stream must exist

Tracing requirements:
For every request, store:
- request_id
- timestamp
- app mode (raw/protected)
- conversation_id
- scenario_id from metadata if present
- whether retrieval was used
- selected retrieval docs
- whether tools were enabled
- tool calls made
- response mode
- canary token id if enabled
- response length
- any structured output validation result
- whether streaming was used
- model name
- error info if request failed

Storage requirements:
- Use simple in-memory stores for:
  - conversations
  - traces
- Keep the code organized so a DB could be added later.
- Create a dedicated storage.py file with small repository-like helpers.

Important realism requirements:
- This app should feel like a real production AI backend, not a benchmark toy.
- It should support multi-turn chat because modern AI apps usually do.
- It should support streaming because real chat products commonly stream responses.
- It should support retrieval because many production assistants are RAG-like.
- It should support optional tool use because modern assistants often call external functions.
- It should keep public API simple and stable.
- It should expose enough metadata to make benchmark attribution and debugging easy.

Important non-goals:
- no frontend
- no database
- no real auth system beyond optional static bearer token
- no real email sending
- no real ticket creation
- no voice / live API
- no multimodal
- no LangGraph or agent framework
- no background workers
- no dependency on the monorepo frontend
- no dependency on internal proxy implementation details unless required for protected routing

Acceptance criteria:
1. I can run the service locally from apps/reference-chat-target with a Gemini API key.
2. I can send a normal chat request and get a text response.
3. I can send a multi-turn request with conversation_id and history is preserved.
4. I can enable streaming and receive SSE chunks.
5. I can switch between raw and protected mode using environment variables only.
6. I can enable retrieval and see selected docs in trace metadata.
7. I can enable tools and inspect any generated tool calls.
8. I can enable canary injection and inspect the canary id in trace metadata.
9. I can fetch conversation history and per-request traces via debug endpoints.
10. The code is clean, typed, and easy to extend for benchmarking.
11. The implementation is self-contained enough that it could later be moved into its own repo with minimal changes.

Also:
- write a small README with curl examples
- include one example for non-streaming
- include one example for streaming
- include one example for structured JSON mode
- include one example with retrieval enabled
- include one example with tools enabled
- include one example with static bearer auth enabled
- include instructions for running locally:
  - pip install -r requirements.txt
  - uvicorn app.main:app --reload --port 8010

README requirements:
- clearly explain that this is a reference benchmark target, not the core product
- explain raw vs protected mode
- explain where to place environment variables
- explain how to use it with benchmark scenarios
- explain that it is intentionally simple but production-like

apps/reference-chat-target/README.md
This app is a realistic benchmark target for AI Protector.
It exists to test, demo, and compare raw vs protected LLM behavior.
It is not part of the core runtime protection service.
