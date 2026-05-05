"""Async SQLAlchemy 2.0 engine, session factory, and FastAPI dependency.

Single source of truth for database connectivity. Use ``get_db`` as a FastAPI
dependency to receive an ``AsyncSession`` per-request, or ``async_session_factory``
directly when you need a session outside of a request context (e.g. workers).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

# ``pool_pre_ping`` lets SQLAlchemy detect stale connections before handing them
# out — essential when the app sits behind a load balancer that may drop idle
# connections. ``pool_recycle`` periodically cycles connections to avoid the
# same problem proactively.
_engine_kwargs: dict[str, Any] = {
    "echo": settings.DB_ECHO,
    "pool_size": settings.DB_POOL_SIZE,
    "max_overflow": settings.DB_MAX_OVERFLOW,
    "pool_timeout": settings.DB_POOL_TIMEOUT,
    "pool_recycle": settings.DB_POOL_RECYCLE,
    "pool_pre_ping": True,
    "future": True,
}

engine: AsyncEngine = create_async_engine(str(settings.DATABASE_URL), **_engine_kwargs)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

# ``expire_on_commit=False`` keeps ORM objects usable after a commit, which is
# almost always what you want in an async web app — otherwise touching any
# attribute after commit triggers an implicit refresh and surprises devs.
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
    class_=AsyncSession,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a database session for the lifetime of a request.

    The session is rolled back on exception and closed on exit. Endpoints
    should *not* commit themselves — let the unit of work / repository layer
    own transactional boundaries explicitly.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def dispose_engine() -> None:
    """Dispose the engine's connection pool. Call from app shutdown hooks."""
    await engine.dispose()
