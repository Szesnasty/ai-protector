"""Red Team test configuration.

Overrides the root conftest's _setup_db autouse fixture so that
red_team tests can run with isolated in-memory SQLite instead of
touching the real PostgreSQL database.

Only creates the red_team tables — never the app's JSONB-based tables.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.red_team.persistence.models import BenchmarkRun, BenchmarkScenarioResult

# Only the red_team tables — NOT the whole Base.metadata
_RED_TEAM_TABLES = [BenchmarkRun.__table__, BenchmarkScenarioResult.__table__]


@pytest.fixture(autouse=True)
async def _setup_db():
    """No-op override — prevents root conftest from hitting real PG for red_team tests."""
    yield


@pytest.fixture
async def engine():
    """Isolated async SQLite engine — only red_team tables."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: BenchmarkRun.metadata.create_all(c, tables=_RED_TEAM_TABLES))
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(lambda c: BenchmarkRun.metadata.drop_all(c, tables=_RED_TEAM_TABLES))
    await eng.dispose()


@pytest.fixture
async def session(engine):
    """Isolated async session for persistence tests."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess
