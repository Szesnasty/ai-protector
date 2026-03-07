"""Shared fixtures for proxy-service tests."""

from __future__ import annotations

import pytest

from src.db.seed import seed_denylist, seed_policies
from src.db.session import engine
from src.models import Base  # noqa: F401 — triggers model registration


@pytest.fixture(autouse=True)
async def _reset_connection_pool():
    """Dispose the SQLAlchemy connection pool between tests.

    Each pytest-asyncio test function gets its own event loop, but the
    engine is a module-level singleton.  Stale pool connections from a
    previous loop cause ``RuntimeError: Future attached to a different
    loop``.  Disposing before each test ensures fresh connections.
    """
    await engine.dispose()

    # Ensure tables exist (mirrors app lifespan for CI/test environments)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await seed_policies()
    await seed_denylist()

    yield
    await engine.dispose()
