"""Wishlist repository: CRUD + item membership."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import Item
from app.models.user import Wishlist, WishlistItem
from app.repositories.base import BaseRepository


class WishlistAlreadyContainsItem(Exception):
    """Raised when the same item is added to a wishlist twice."""


class WishlistRepository(BaseRepository[Wishlist]):
    model = Wishlist

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Wishlist)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Wishlist]:
        """All wishlists owned by a user, newest first."""
        stmt = (
            select(Wishlist)
            .where(Wishlist.user_id == user_id)
            .order_by(Wishlist.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_share_token(self, token: str) -> Wishlist | None:
        """Look up a publicly-shared wishlist by its share token."""
        stmt = select(Wishlist).where(
            Wishlist.share_token == token,
            Wishlist.is_public.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_items(self, wishlist_id: uuid.UUID) -> Wishlist | None:
        """Fetch a wishlist with its items + each item's tags eagerly loaded."""
        stmt = (
            select(Wishlist)
            .where(Wishlist.id == wishlist_id)
            .options(
                selectinload(Wishlist.items)
                .selectinload(WishlistItem.item)
                .selectinload(Item.tags),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # --------------------------------------------------------- membership
    async def add_item(
        self,
        wishlist_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        priority: str = "normal",
        notes: str | None = None,
    ) -> WishlistItem:
        """Add an item to a wishlist. Raises if already present."""
        entry = WishlistItem(
            wishlist_id=wishlist_id,
            item_id=item_id,
            priority=priority,
            notes=notes,
        )
        self.session.add(entry)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise WishlistAlreadyContainsItem(
                f"Item {item_id} is already in wishlist {wishlist_id}"
            ) from exc
        return entry

    async def remove_item(self, wishlist_id: uuid.UUID, item_id: uuid.UUID) -> bool:
        """Remove an item; returns True if a row was actually deleted."""
        stmt = sa_delete(WishlistItem).where(
            WishlistItem.wishlist_id == wishlist_id,
            WishlistItem.item_id == item_id,
        )
        result = await self.session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def mark_purchased(
        self, wishlist_id: uuid.UUID, item_id: uuid.UUID, *, purchased: bool = True
    ) -> bool:
        """Toggle the ``is_purchased`` flag on a wishlist entry."""
        stmt = (
            WishlistItem.__table__.update()
            .where(
                WishlistItem.wishlist_id == wishlist_id,
                WishlistItem.item_id == item_id,
            )
            .values(is_purchased=purchased)
        )
        result = await self.session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def get_items(self, wishlist_id: uuid.UUID) -> Sequence[WishlistItem]:
        """Just the WishlistItem rows (no eager item load) for membership checks."""
        stmt = select(WishlistItem).where(WishlistItem.wishlist_id == wishlist_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
