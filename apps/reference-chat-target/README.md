# Reference Chat Target

A realistic benchmark target for **AI Protector** security testing.

This is **not** the core product service. It exists to test, demo, and compare raw vs protected LLM behavior. It is intentionally simple but production-like — multi-turn chat, streaming, retrieval, tools, and canary injection are all supported.

## Quick Start

```bash
cd apps/reference-chat-target

# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key
export GEMINI_API_KEY="your-key-here"

# Run the service
uvicorn app.main:app --reload --port 8010
```

## Configuration

Copy `.env.example` to `.env` and fill in values. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | **Required** for raw mode |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `APP_MODE` | `raw` | `raw` = direct Gemini, `protected` = via AI Protector |
| `AI_PROTECTOR_BASE_URL` | — | Required when `APP_MODE=protected` |
| `AI_PROTECTOR_API_KEY` | — | Bearer token for AI Protector |
| `ENABLE_STREAMING` | `true` | Enable SSE streaming |
| `ENABLE_RETRIEVAL` | `true` | Enable knowledge-base retrieval |
| `ENABLE_TOOLS` | `false` | Enable mock tool calling |
| `ENABLE_STRUCTURED_OUTPUT` | `true` | Enable JSON response mode |
| `ENABLE_CANARY` | `true` | Inject canary tokens into system prompt |
| `STATIC_AUTH_TOKEN` | — | If set, require `Bearer <token>` on API calls |
| `PORT` | `8010` | Server port |

## Modes

### Raw mode (`APP_MODE=raw`)
Calls Gemini directly via the Google GenAI SDK. No proxy, no protection layer.

### Protected mode (`APP_MODE=protected`)
Routes model requests through AI Protector's OpenAI-compatible endpoint at `{AI_PROTECTOR_BASE_URL}/v1/chat/completions`. The external API contract stays identical — only the backend path changes.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/v1/chat` | Yes* | Chat (text or structured JSON; supports `stream=true`) |
| `POST` | `/v1/chat/stream` | Yes* | Chat with SSE streaming |
| `GET` | `/v1/conversations/{id}` | Yes* | Conversation history |
| `GET` | `/v1/traces/{id}` | Yes* | Request trace metadata |
| `GET` | `/health` | No | Service health and config |

*Auth required only when `STATIC_AUTH_TOKEN` is configured.

## Examples

### Basic chat
```bash
curl -s http://localhost:8010/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is your refund policy?"}]
  }' | jq .
```

### Multi-turn conversation
```bash
# First turn
curl -s http://localhost:8010/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "I want to return an item"}]
  }' | jq .conversation_id
# Returns: "abc-123..."

# Second turn (pass conversation_id)
curl -s http://localhost:8010/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "abc-123...",
    "messages": [{"role": "user", "content": "The order number is ORD-55555"}]
  }' | jq .
```

### Streaming (SSE)
```bash
curl -N http://localhost:8010/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Tell me about shipping options"}]
  }'
```

### Structured JSON output
```bash
curl -s http://localhost:8010/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "My account is locked, what should I do?"}],
    "response_mode": "json"
  }' | jq .structured_output
```

### With retrieval
```bash
curl -s http://localhost:8010/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "How do refunds work?"}],
    "use_retrieval": true
  }' | jq .citations
```

### With tools enabled
```bash
curl -s http://localhost:8010/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Check the status of order ORD-12345"}],
    "use_tools": true
  }' | jq .tool_calls
```

### With bearer auth
```bash
export STATIC_AUTH_TOKEN=my-secret-token
# restart server, then:
curl -s http://localhost:8010/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-secret-token" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}]
  }' | jq .
```

### Health check
```bash
curl -s http://localhost:8010/health | jq .
```

## Using with Benchmarks

This service is designed as a target for AI Protector's red-team benchmark runner. Typical usage:

1. **Raw baseline:** Run benchmarks against `http://localhost:8010` with `APP_MODE=raw` to measure how the model behaves without protection.
2. **Protected run:** Switch to `APP_MODE=protected` with AI Protector configured. Re-run the same benchmarks. Compare scores.
3. **Canary scenarios:** With `ENABLE_CANARY=true`, each request injects a unique canary token. Benchmark detectors check if the canary leaks in responses.
4. **Trace inspection:** After a run, use `/v1/traces/{request_id}` to inspect what happened per-request — retrieval docs, tool calls, canary IDs, errors.

## Architecture

```
Client → POST /v1/chat
           │
           ├─ raw mode → GeminiDirectBackend → Google GenAI SDK → Gemini API
           │
           └─ protected mode → ProtectedHTTPBackend → HTTP → AI Protector → Gemini
```

The `ModelBackend` abstraction keeps mode-switching invisible to the chat service layer.

## Non-goals

- No frontend
- No database (in-memory only, FIFO eviction)
- No real auth system beyond static bearer token
- No real side effects (tools are mocks)
- No dependency on core AI Protector code
