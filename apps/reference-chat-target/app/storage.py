"""In-memory storage for conversations and traces with FIFO eviction."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone

from app.config import Settings
from app.models import ChatMessage, Conversation, TraceRecord


class ConversationStore:
    def __init__(self, max_items: int = 200, max_messages: int = 50) -> None:
        self._data: OrderedDict[str, Conversation] = OrderedDict()
        self._max_items = max_items
        self._max_messages = max_messages

    def get(self, conversation_id: str) -> Conversation | None:
        return self._data.get(conversation_id)

    def create(self, conversation_id: str) -> Conversation:
        conv = Conversation(conversation_id=conversation_id)
        self._put(conversation_id, conv)
        return conv

    def get_or_create(self, conversation_id: str) -> Conversation:
        existing = self.get(conversation_id)
        if existing is not None:
            return existing
        return self.create(conversation_id)

    def append_messages(
        self, conversation_id: str, messages: list[ChatMessage]
    ) -> None:
        conv = self._data.get(conversation_id)
        if conv is None:
            return
        conv.messages.extend(messages)
        if len(conv.messages) > self._max_messages:
            conv.messages = conv.messages[-self._max_messages :]
        conv.updated_at = datetime.now(timezone.utc)
        self._data.move_to_end(conversation_id)

    def _put(self, key: str, value: Conversation) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self._max_items:
            self._data.popitem(last=False)


class TraceStore:
    def __init__(self, max_items: int = 1000) -> None:
        self._data: OrderedDict[str, TraceRecord] = OrderedDict()
        self._max_items = max_items

    def get(self, request_id: str) -> TraceRecord | None:
        return self._data.get(request_id)

    def put(self, trace: TraceRecord) -> None:
        self._data[trace.request_id] = trace
        self._data.move_to_end(trace.request_id)
        while len(self._data) > self._max_items:
            self._data.popitem(last=False)


def create_stores(settings: Settings) -> tuple[ConversationStore, TraceStore]:
    return (
        ConversationStore(
            max_items=settings.max_conversations,
            max_messages=settings.max_messages_per_conversation,
        ),
        TraceStore(max_items=settings.max_traces),
    )
