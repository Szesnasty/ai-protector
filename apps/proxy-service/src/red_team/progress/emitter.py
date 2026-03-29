"""In-memory pub/sub progress emitter for benchmark runs."""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import AsyncGenerator

from src.red_team.progress.events import ProgressEvent, event_type_for, is_terminal
from src.red_team.progress.formatter import format_sse


class ProgressEmitter:
    """Pub/sub emitter that fans out SSE-formatted progress events per run_id.

    Usage::

        emitter = ProgressEmitter()

        # In subscriber (e.g. SSE endpoint):
        async for sse_line in emitter.subscribe(run_id):
            yield sse_line

        # In run engine:
        await emitter.emit(run_id, ScenarioStartEvent(...))
    """

    def __init__(self) -> None:
        # run_id → list of subscriber queues
        self._subscribers: dict[uuid.UUID, list[asyncio.Queue[str | None]]] = defaultdict(list)

    async def emit(self, run_id: uuid.UUID, event: ProgressEvent) -> None:
        """Push an SSE-formatted event to all subscribers of *run_id*."""
        sse_text = format_sse(event)
        queues = self._subscribers.get(run_id, [])
        for q in queues:
            q.put_nowait(sse_text)

        # If this is a terminal event, signal subscribers to stop.
        event_type = event_type_for(event)
        if is_terminal(event_type):
            for q in queues:
                q.put_nowait(None)  # sentinel
            self._cleanup(run_id)

    async def subscribe(self, run_id: uuid.UUID) -> AsyncGenerator[str, None]:
        """Yield SSE-formatted strings for *run_id* until the run ends."""
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._subscribers[run_id].append(queue)
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            # Remove this queue from subscriber list (idempotent).
            subs = self._subscribers.get(run_id, [])
            if queue in subs:
                subs.remove(queue)
            if not subs and run_id in self._subscribers:
                del self._subscribers[run_id]

    def subscriber_count(self, run_id: uuid.UUID) -> int:
        """Return the number of active subscribers for *run_id*."""
        return len(self._subscribers.get(run_id, []))

    def _cleanup(self, run_id: uuid.UUID) -> None:
        """Remove all subscriber queues for a completed run."""
        self._subscribers.pop(run_id, None)
