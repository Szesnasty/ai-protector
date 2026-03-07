"""Shared fixtures for proxy-service tests."""

from __future__ import annotations

import pytest

from src.db.seed import seed_denylist, seed_policies
from src.db.session import engine
from src.models import Base  # noqa: F401 — triggers model registration

_db_seeded = False


@pytest.fixture(autouse=True)
async def _setup_db():
    """Manage DB lifecycle for each test.

    * **Engine dispose** runs before every test — each pytest-asyncio
      test function gets its own event loop, but the engine is a
      module-level singleton.  Disposing prevents ``RuntimeError:
      Future attached to a different loop``.
    * **Table creation + seeding** runs only once (first test).
      ``create_all`` is DDL-idempotent and the seed helpers use
      INSERT-IF-NOT-EXISTS, so running them once per session is safe.
      Tests that mutate policies use unique names and clean up after
      themselves.
    """
    global _db_seeded  # noqa: PLW0603

    await engine.dispose()

    if not _db_seeded:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await seed_policies()
        await seed_denylist()
        _db_seeded = True

    yield
    await engine.dispose()
