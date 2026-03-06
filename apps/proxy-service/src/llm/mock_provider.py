"""Mock LLM provider for demo mode.

Returns deterministic fixture responses based on the pipeline's intent
classification.  The security pipeline runs for real — only the final
LLM call is replaced.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

MOCK_RESPONSES: dict[str, list[str]] = {
    "qa": [
        (
            "Based on our documentation, the standard return policy allows "
            "returns within 30 days of purchase with a valid receipt. Items "
            "must be in their original packaging and unused condition."
        ),
        (
            "Our business hours are Monday through Friday, 9 AM to 6 PM EST. "
            "Weekend support is available via email with a 24-hour response time."
        ),
        (
            "The recommended approach is to check the documentation first. "
            "If the issue persists, our support team can help troubleshoot "
            "the specific configuration."
        ),
    ],
    "code_gen": [
        (
            "```python\n"
            "def process_order(order_id: str, status: str = 'pending') -> dict:\n"
            '    """Process an order and return updated status."""\n'
            "    if not order_id.startswith('ORD-'):\n"
            "        raise ValueError(f'Invalid order ID: {order_id}')\n"
            "    return {'order_id': order_id, 'status': status, 'updated': True}\n"
            "```"
        ),
    ],
    "chitchat": [
        (
            "Hello! I'm here to help. Feel free to ask me anything about our "
            "services, or try one of the attack scenarios from the sidebar to "
            "see the firewall in action."
        ),
        (
            "Hi there! You can test the security pipeline by selecting an "
            "attack scenario, or ask me a regular question to see the normal flow."
        ),
    ],
    "tool_call": [
        "I'll help you with that. Let me look up the relevant information.",
    ],
}

FALLBACK_RESPONSE = (
    "I can help with that! This is a demo environment \u2014 the security pipeline "
    "you just saw is running for real (NeMo Guardrails, Presidio PII detection, "
    "custom rules). Try an attack scenario from the sidebar to see it block threats."
)

MOCK_MODEL_ID = "mock-demo"


def _pick_response(intent: str) -> str:
    """Pick a random fixture response for the given intent."""
    responses = MOCK_RESPONSES.get(intent, [FALLBACK_RESPONSE])
    return random.choice(responses)  # noqa: S311


def mock_completion(
    messages: list[dict[str, Any]],
    intent: str = "",
    stream: bool = False,
) -> dict[str, Any]:
    """Return a mock OpenAI-compatible completion response.

    Args:
        messages: Conversation messages (used for token estimation).
        intent: Pipeline intent classification (qa, code_gen, chitchat, ...).
        stream: Ignored here; use :func:`mock_completion_stream` for streaming.

    Returns:
        Dict matching the OpenAI ``chat.completion`` response shape.
    """
    content = _pick_response(intent)

    prompt_tokens = sum(len(m.get("content", "").split()) for m in messages)
    completion_tokens = len(content.split())

    return {
        "id": f"chatcmpl-mock-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
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
    }


class _MockDelta:
    """Minimal delta object compatible with sse_stream expectations."""

    def __init__(self, *, role: str | None = None, content: str | None = None) -> None:
        self.role = role
        self.content = content


class _MockChoice:
    """Minimal choice object compatible with sse_stream expectations."""

    def __init__(self, delta: _MockDelta, finish_reason: str | None = None) -> None:
        self.delta = delta
        self.finish_reason = finish_reason


class _MockChunk:
    """Minimal chunk object compatible with sse_stream expectations."""

    def __init__(self, choices: list[_MockChoice]) -> None:
        self.choices = choices


async def mock_completion_stream(
    messages: list[dict[str, Any]],
    intent: str = "",
) -> Any:
    """Async generator yielding mock chunks compatible with ``sse_stream()``.

    Yields word-by-word for a realistic streaming feel.
    """
    content = _pick_response(intent)
    words = content.split()

    # Yield initial role chunk
    yield _MockChunk(choices=[_MockChoice(delta=_MockDelta(role="assistant"), finish_reason=None)])

    for i, word in enumerate(words):
        is_last = i == len(words) - 1
        token = word if is_last else word + " "
        yield _MockChunk(
            choices=[
                _MockChoice(
                    delta=_MockDelta(content=token),
                    finish_reason="stop" if is_last else None,
                )
            ]
        )
        await asyncio.sleep(0.02)  # 20 ms between words
