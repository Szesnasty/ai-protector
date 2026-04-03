# 01 — Mock Provider + MODE

> **Priority:** Critical | **Effort:** 4–6h | **Dependencies:** none

---

## Goal

Allow AI Protector to run without any LLM backend (no Ollama, no API keys). The security pipeline runs for real. Only the final LLM call is replaced by a MockProvider that returns deterministic fixture responses based on the pipeline's intent classification.

---

## Design

### 1.1 New env var: `MODE`

| Value | Behavior |
|-------|----------|
| `demo` (default) | MockProvider is the LLM backend. Ollama not required. |
| `real` | Current behavior — Ollama or external provider via API key. |

**Proxy-service** — `src/config.py`:
```python
class Settings(BaseSettings):
    # ... existing fields ...
    mode: str = "demo"  # "demo" | "real"
```

**Agent-demo** — `src/config.py`:
```python
class Settings(BaseSettings):
    # ... existing fields ...
    mode: str = "demo"  # "demo" | "real"
```

Both read from `MODE=demo` in `.env` (or env var).

### 1.2 API key overlay (both modes)

If a user has pasted an API key in Settings UI → `x-api-key` header is present → use real provider **regardless of MODE**. This means:

```
MODE=demo + no API key     → MockProvider
MODE=demo + API key given  → Real provider (OpenAI/Anthropic/etc.)
MODE=real + no API key     → Ollama (as today)
MODE=real + API key given  → Real provider (as today)
```

Decision logic in `llm_completion()`:
```
if api_key is provided:
    → use real provider (existing code)
elif mode == "demo":
    → use MockProvider
else:
    → use Ollama (existing code)
```

---

## 2. MockProvider Implementation

### 2.1 Proxy-service: `src/llm/mock_provider.py`

```python
"""Mock LLM provider for demo mode — returns fixture responses by intent."""

from __future__ import annotations

import time
import random
from typing import Any

MOCK_RESPONSES: dict[str, list[str]] = {
    "qa": [
        "Based on our documentation, the standard return policy allows returns within 30 days of purchase with a valid receipt. Items must be in their original packaging and unused condition.",
        "Our business hours are Monday through Friday, 9 AM to 6 PM EST. Weekend support is available via email with a 24-hour response time.",
        "The recommended approach is to check the documentation first. If the issue persists, our support team can help troubleshoot the specific configuration.",
    ],
    "code_gen": [
        "```python\ndef process_order(order_id: str, status: str = 'pending') -> dict:\n    \"\"\"Process an order and return updated status.\"\"\"\n    if not order_id.startswith('ORD-'):\n        raise ValueError(f'Invalid order ID: {order_id}')\n    return {'order_id': order_id, 'status': status, 'updated': True}\n```",
    ],
    "chitchat": [
        "Hello! I'm here to help. Feel free to ask me anything about our services, or try one of the attack scenarios from the sidebar to see the firewall in action.",
        "Hi there! You can test the security pipeline by selecting an attack scenario, or ask me a regular question to see the normal flow.",
    ],
    "tool_call": [
        "I'll help you with that. Let me look up the relevant information.",
    ],
}

FALLBACK_RESPONSE = (
    "I can help with that! This is a demo environment — the security pipeline "
    "you just saw is running for real (NeMo Guardrails, Presidio PII detection, "
    "custom rules). Try an attack scenario from the sidebar to see it block threats."
)

MOCK_MODEL_ID = "mock-demo"


def mock_completion(
    messages: list[dict[str, Any]],
    intent: str = "",
    stream: bool = False,
) -> dict[str, Any]:
    """Generate a mock LLM response.

    Args:
        messages: The conversation messages (used for context).
        intent: Intent classified by the pipeline (qa, code_gen, chitchat, tool_call).
        stream: If True, returns a format compatible with streaming (single chunk).

    Returns:
        OpenAI-compatible response dict.
    """
    responses = MOCK_RESPONSES.get(intent, [FALLBACK_RESPONSE])
    content = random.choice(responses)

    # Simulate realistic latency (50–150ms)
    latency_ms = random.randint(50, 150)
    time.sleep(latency_ms / 1000)

    prompt_tokens = sum(len(m.get("content", "").split()) for m in messages)
    completion_tokens = len(content.split())

    return {
        "id": f"chatcmpl-mock-{int(time.time())}",
        "object": "chat.completion",
        "model": MOCK_MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "_mock": True,
        "_latency_ms": latency_ms,
    }
```

### 2.2 Integration point: `src/llm/client.py`

Modify `llm_completion()` to check mode before calling LiteLLM:

```python
async def llm_completion(messages, model, stream=False, temperature=None, max_tokens=None, api_key=None):
    settings = get_settings()

    # API key override — always use real provider if key provided
    if api_key:
        # ... existing real provider code (unchanged) ...
        pass

    # Demo mode — use MockProvider
    elif settings.mode == "demo":
        from src.llm.mock_provider import mock_completion
        intent = ""  # Will be passed from pipeline state — see 2.3
        return mock_completion(messages, intent=intent, stream=stream)

    # Real mode — existing Ollama/LiteLLM code
    else:
        # ... existing code (unchanged) ...
        pass
```

### 2.3 Intent passthrough

The pipeline already classifies intent in `intent_node` and stores it in `PipelineState["intent"]`. The `llm_call_node` in proxy-service needs to pass `intent` to `llm_completion()`.

**File:** `src/pipeline/nodes/llm_call.py`

Add `intent` parameter:
```python
async def llm_call_node(state: PipelineState) -> PipelineState:
    intent = state.get("intent", "")
    # ... pass intent to llm_completion(messages, model, intent=intent, ...)
```

Update `llm_completion()` signature to accept optional `intent: str = ""`.

### 2.4 Streaming support for mock

For streaming mode, MockProvider yields a single SSE chunk with the full content (simulating instant-complete stream). This is simpler than chunking and works with the existing frontend streaming parser. Alternatively, chunk the response into words with small delays for a more realistic feel.

```python
async def mock_completion_stream(messages, intent=""):
    """Async generator yielding SSE-compatible chunks."""
    response = mock_completion(messages, intent=intent)
    content = response["choices"][0]["message"]["content"]

    # Yield word by word for realistic streaming feel
    words = content.split()
    for i, word in enumerate(words):
        chunk = {
            "id": response["id"],
            "object": "chat.completion.chunk",
            "model": MOCK_MODEL_ID,
            "choices": [{
                "index": 0,
                "delta": {"content": word + (" " if i < len(words) - 1 else "")},
                "finish_reason": None if i < len(words) - 1 else "stop",
            }],
        }
        yield chunk
        await asyncio.sleep(0.02)  # 20ms between words
```

---

## 3. Agent-demo MockProvider

### 3.1 Problem

Agent-demo calls LLM **through the proxy** (`acompletion()` → `proxy_base_url`). In demo mode the proxy will use MockProvider, so agent-demo gets mock responses automatically.

**However:** Agent-demo's LLM call expects the model to return tool calls (JSON with `tool_calls` array). MockProvider in the proxy won't generate tool-call JSON — it returns plain text.

### 3.2 Solution: Agent-aware mock responses

When `MODE=demo` in proxy-service and the request comes from agent-demo (detectable by `x-client-id: agent-*`), the MockProvider should return responses that match what the agent expects:

1. **If the last user message looks like it needs a tool** (e.g., "check order status") → return a mock tool_call response.
2. **If tool results are in context** (messages contain `role: tool`) → return a plain text summary.
3. **Otherwise** → return a general helpful response.

```python
AGENT_TOOL_TRIGGERS: dict[str, dict] = {
    "order": {
        "name": "getOrderStatus",
        "arguments": '{"order_id": "ORD-123"}',
    },
    "knowledge": {
        "name": "searchKnowledgeBase",
        "arguments": '{"query": "return policy"}',
    },
}
```

**Alternative (simpler):** Agent-demo has its own `MODE` check. When `MODE=demo`, the `llm_call_node` in agent-demo uses its own mock that understands the agent's tool schema, bypassing the proxy for the LLM call entirely. The proxy is still called for non-mock scenarios (API key provided).

**Recommendation:** Alternative approach is cleaner. Agent-demo gets its own `src/agent/mock_llm.py` with agent-specific mock responses. The proxy MockProvider handles playground/compare page only.

### 3.3 Agent-demo mock: `src/agent/mock_llm.py`

```python
"""Mock LLM for agent-demo in demo mode.

Returns responses that trigger tool calls or summarize tool results,
matching the agent's expected LLM behavior.
"""

TOOL_CALL_RESPONSE = {
    "order": {"name": "getOrderStatus", "arguments": {"order_id": "ORD-123"}},
    "knowledge": {"name": "searchKnowledgeBase", "arguments": {"query": "return policy"}},
    "profile": {"name": "getCustomerProfile", "arguments": {"customer_id": "C-001"}},
}

SUMMARY_RESPONSES = [
    "Based on the information I found, here's what I can tell you: {tool_summary}",
    "I've looked into that for you. {tool_summary}",
]
```

Integration in `src/agent/nodes/llm_call.py`:
```python
async def llm_call_node(state: AgentState) -> AgentState:
    settings = get_settings()
    api_key = state.get("api_key")

    # API key override → always use real provider (through proxy)
    if api_key:
        # ... existing proxy call code ...
        pass

    # Demo mode → use agent mock
    elif settings.mode == "demo":
        from src.agent.mock_llm import mock_agent_llm
        return mock_agent_llm(state)

    # Real mode → existing proxy call
    else:
        # ... existing code ...
        pass
```

---

## 4. Files to create / modify

### New files:
| File | Purpose |
|------|---------|
| `apps/proxy-service/src/llm/mock_provider.py` | MockProvider for proxy pipeline |
| `apps/agent-demo/src/agent/mock_llm.py` | Mock LLM for agent tool-calling flow |

### Modified files:
| File | Change |
|------|--------|
| `apps/proxy-service/src/config.py` | Add `mode: str = "demo"` |
| `apps/proxy-service/src/llm/client.py` | Branch on `mode` + `api_key` |
| `apps/proxy-service/src/pipeline/nodes/llm_call.py` | Pass `intent` to `llm_completion()` |
| `apps/agent-demo/src/config.py` | Add `mode: str = "demo"` |
| `apps/agent-demo/src/agent/nodes/llm_call.py` | Branch on `mode` + `api_key` |
| `infra/.env` | Add `MODE=demo` |
| `infra/.env.example` | Add `MODE=demo` with comments |

---

## 5. Test plan

| Test | What to verify |
|------|---------------|
| `test_mock_provider.py` | MockProvider returns valid OpenAI-format responses per intent |
| `test_mock_streaming.py` | Streaming mock yields correct SSE chunks |
| `test_mode_routing.py` | `MODE=demo` → mock; `MODE=real` → LiteLLM; `api_key` → always real |
| `test_agent_mock.py` | Agent mock returns tool calls and summaries correctly |
| Manual: playground | Prompt in demo mode → pipeline runs → mock response appears |
| Manual: scenarios | Attack scenario → BLOCK (real pipeline); safe scenario → ALLOW + mock response |
| Manual: API key overlay | Paste OpenAI key → get real GPT response even in demo mode |

---

## 6. Key decisions

1. **Default MODE is `demo`** — zero friction for new users.
2. **Mock responses are short and useful** — not "lorem ipsum", but realistic customer support answers.
3. **API key always overrides mock** — seamless upgrade path.
4. **Agent-demo has its own mock** — cleaner than trying to make proxy MockProvider understand tool-calling.
5. **Streaming mock yields word-by-word** — feels natural in the UI.
