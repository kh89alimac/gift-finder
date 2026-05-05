"""Unit of Work — composes all repositories under one ``AsyncSession``.

A unit of work owns a session and a transaction. Use it as an async context
manager for any operation that touches multiple aggregates: the transaction
commits on clean exit and rolls back on any exception. Inside, all repos
share the same session so their writes commit (or fail) together.

Example::

    async with UnitOfWork(session_factory) as uow:
        item = await uow.items.get_by_id_or_raise(item_id)
        await uow.wishlists.add_item(wishlist_id, item.id)
        await uow.recommendations.upsert_signal(user_id, tag_id, score_delta=1)
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import async_session_factory as default_session_factory
from app.repositories.instagram import InstagramQueueRepository
from app.repositories.items import ItemRepository
from app.repositories.recommendations import RecommendationRepository
from app.repositories.scraper_jobs import ScraperJobRepository
from app.repositories.tags import TagRepository
from app.repositories.wishlists import WishlistRepository


class UnitOfWork:
    """Aggregate root for a single transactional scope.

    Pass a custom ``session_factory`` for testing (e.g. one bound to a
    rollback-only session).
    """

    session: AsyncSession

    items: ItemRepository
    wishlists: WishlistRepository
    tags: TagRepository
    scraper_jobs: ScraperJobRepository
    instagram: InstagramQueueRepository
    recommendations: RecommendationRepository

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_factory = session_factory or default_session_factory
        self._committed = False

    # ------------------------------------------------------------- enter
    async def __aenter__(self) -> Self:
        self.session = self._session_factory()
        # Build repositories now so callers can use them without extra setup.
        self.items = ItemRepository(self.session)
        self.wishlists = WishlistRepository(self.session)
        self.tags = TagRepository(self.session)
        self.scraper_jobs = ScraperJobRepository(self.session)
        self.instagram = InstagramQueueRepository(self.session)
        self.recommendations = RecommendationRepository(self.session)
        return self

    # -------------------------------------------------------------- exit
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.session.rollback()
            elif not self._committed:
                # Auto-commit on clean exit so callers can simply `async with`.
                await self.session.commit()
        finally:
            await self.session.close()

    # --------------------------------------------------- explicit control
    async def commit(self) -> None:
        """Commit the active transaction explicitly.

        Useful when you want to commit mid-block and continue working — e.g.
        commit a scrape result then start another transaction in the same
        unit. After this returns, ``self.session`` is still open.
        """
        await self.session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """Roll back without raising. Subsequent ``__aexit__`` will not commit."""
        await self.session.rollback()
        self._committed = True  # prevent the auto-commit on exit
