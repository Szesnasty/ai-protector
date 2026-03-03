"""In-memory session store for agent conversations."""

from __future__ import annotations

import structlog

from src.config import get_settings

logger = structlog.get_logger()


class SessionStore:
    """Simple in-memory session store keyed by session_id."""

    def __init__(self, max_sessions: int | None = None, max_turns: int | None = None) -> None:
        settings = get_settings()
        self._max_sessions = max_sessions or settings.max_sessions
        self._max_turns = max_turns or settings.max_turns
        self._sessions: dict[str, list[dict]] = {}

    def get_history(self, session_id: str) -> list[dict]:
        """Return chat history for session (empty list if new)."""
        return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, role: str, content: str) -> None:
        """Append a message to session history, trim if needed."""
        if session_id not in self._sessions:
            # Evict oldest session if at capacity
            if len(self._sessions) >= self._max_sessions:
                oldest_key = next(iter(self._sessions))
                del self._sessions[oldest_key]
                logger.info("session_evicted", session_id=oldest_key)
            self._sessions[session_id] = []

        self._sessions[session_id].append({"role": role, "content": content})

        # Trim to max_turns (keep system message + last N messages)
        history = self._sessions[session_id]
        if len(history) > self._max_turns * 2:
            # Keep first message (system) + last max_turns*2 messages
            self._sessions[session_id] = history[:1] + history[-(self._max_turns * 2 - 1) :]

    def clear(self, session_id: str) -> None:
        """Clear a specific session."""
        self._sessions.pop(session_id, None)

    def session_count(self) -> int:
        """Return number of active sessions."""
        return len(self._sessions)


# Singleton instance
session_store = SessionStore()
