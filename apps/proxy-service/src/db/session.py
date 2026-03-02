"""Async database session factory and Redis client."""

from collections.abc import AsyncGenerator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session (FastAPI dependency)."""
    async with async_session() as session:
        yield session


_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """Return a shared Redis client (lazy-initialized)."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def close_db() -> None:
    """Dispose the SQLAlchemy engine."""
    await engine.dispose()


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
