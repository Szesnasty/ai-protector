"""Shared fixtures for proxy-service tests."""

from __future__ import annotations

import pytest

from src.db.session import engine


@pytest.fixture(autouse=True)
async def _reset_connection_pool():
    """Dispose the SQLAlchemy connection pool between tests.

    Each pytest-asyncio test function gets its own event loop, but the
    engine is a module-level singleton.  Stale pool connections from a
    previous loop cause ``RuntimeError: Future attached to a different
    loop``.  Disposing before each test ensures fresh connections.
    """
    await engine.dispose()
    yield
    await engine.dispose()
