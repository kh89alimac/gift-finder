"""Wishlist service: CRUD, items, share-token sharing."""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy import func, select

from app.core.config import settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.user import Wishlist, WishlistItem
from app.repositories.unit_of_work import UnitOfWork
from app.repositories.wishlists import WishlistAlreadyContainsItem
from app.schemas.wishlists import (
    AddToWishlistRequest,
    ShareTokenResponse,
    WishlistCreate,
    WishlistDetail,
    WishlistItemOut,
    WishlistSummary,
    WishlistUpdate,
)
from app.schemas.items import ItemSummary


class WishlistService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # --------------------------------------------------------------- list
    async def list_for_user(self, user_id: uuid.UUID) -> list[WishlistSummary]:
        wishlists = await self.uow.wishlists.list_for_user(user_id)
        # Counts in one extra query (cheaper than per-row N+1).
        counts = await self._counts(user_id)
        return [
            WishlistSummary(
                id=w.id,
                user_id=w.user_id,
                name=w.name,
                description=w.description,
                is_public=w.is_public,
                item_count=counts.get(w.id, 0),
                created_at=w.created_at,
                updated_at=w.updated_at,
            )
            for w in wishlists
        ]

    async def _counts(self, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
        stmt = (
            select(WishlistItem.wishlist_id, func.count(WishlistItem.id))
            .join(Wishlist, Wishlist.id == WishlistItem.wishlist_id)
            .where(Wishlist.user_id == user_id)
            .group_by(WishlistItem.wishlist_id)
        )
        result = await self.uow.session.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}

    # ------------------------------------------------------------- create
    async def create_wishlist(
        self, user_id: uuid.UUID, data: WishlistCreate
    ) -> WishlistDetail:
        wishlist = await self.uow.wishlists.create(
            user_id=user_id,
            name=data.name,
            description=data.description,
            is_public=data.is_public,
        )
        return self._to_detail(wishlist, items=[])

    # ---------------------------------------------------------------- get
    async def get_wishlist(
        self,
        wishlist_id: uuid.UUID,
        requesting_user_id: uuid.UUID | None,
    ) -> WishlistDetail:
        wishlist = await self.uow.wishlists.get_with_items(wishlist_id)
        if wishlist is None:
            raise NotFoundError(f"Wishlist {wishlist_id} not found")
        if not wishlist.is_public and wishlist.user_id != requesting_user_id:
            raise ForbiddenError("You do not have access to this wishlist")
        return self._to_detail(wishlist, items=list(wishlist.items))

    async def get_by_share_token(self, token: str) -> WishlistDetail:
        wishlist = await self.uow.wishlists.get_by_share_token(token)
        if wishlist is None:
            raise NotFoundError("Shared wishlist not found")
        # Re-fetch with eager loads — get_by_share_token doesn't include items.
        full = await self.uow.wishlists.get_with_items(wishlist.id)
        assert full is not None
        return self._to_detail(full, items=list(full.items))

    # ------------------------------------------------------------- update
    async def update_wishlist(
        self,
        wishlist_id: uuid.UUID,
        user_id: uuid.UUID,
        data: WishlistUpdate,
    ) -> WishlistDetail:
        wishlist = await self.uow.wishlists.get_by_id(wishlist_id)
        if wishlist is None:
            raise NotFoundError(f"Wishlist {wishlist_id} not found")
        if wishlist.user_id != user_id:
            raise ForbiddenError("Cannot modify someone else's wishlist")
        changes = data.model_dump(exclude_unset=True)
        if changes:
            await self.uow.wishlists.update(wishlist, **changes)
        full = await self.uow.wishlists.get_with_items(wishlist.id)
        assert full is not None
        return self._to_detail(full, items=list(full.items))

    # ------------------------------------------------------------- delete
    async def delete_wishlist(self, wishlist_id: uuid.UUID, user_id: uuid.UUID) -> None:
        wishlist = await self.uow.wishlists.get_by_id(wishlist_id)
        if wishlist is None:
            raise NotFoundError(f"Wishlist {wishlist_id} not found")
        if wishlist.user_id != user_id:
            raise ForbiddenError("Cannot delete someone else's wishlist")
        await self.uow.wishlists.delete(wishlist)

    # --------------------------------------------------------------- items
    async def add_item(
        self,
        wishlist_id: uuid.UUID,
        user_id: uuid.UUID,
        data: AddToWishlistRequest,
    ) -> WishlistItemOut:
        wishlist = await self.uow.wishlists.get_by_id(wishlist_id)
        if wishlist is None:
            raise NotFoundError(f"Wishlist {wishlist_id} not found")
        if wishlist.user_id != user_id:
            raise ForbiddenError("Cannot modify someone else's wishlist")

        # Confirm item exists before we insert — gives a 404 instead of a 409
        # when the FK is bad.
        item = await self.uow.items.get_by_id(data.item_id)
        if item is None:
            raise NotFoundError(f"Item {data.item_id} not found")

        try:
            entry = await self.uow.wishlists.add_item(
                wishlist_id,
                data.item_id,
                priority=data.priority,
                notes=data.notes,
            )
        except WishlistAlreadyContainsItem as exc:
            raise ConflictError(str(exc)) from exc

        return WishlistItemOut(
            id=entry.id,
            wishlist_id=entry.wishlist_id,
            item_id=entry.item_id,
            priority=entry.priority,
            notes=entry.notes,
            is_purchased=entry.is_purchased,
            added_at=entry.added_at,
            item=ItemSummary.model_validate(item),
        )

    async def remove_item(
        self,
        wishlist_id: uuid.UUID,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> None:
        wishlist = await self.uow.wishlists.get_by_id(wishlist_id)
        if wishlist is None:
            raise NotFoundError(f"Wishlist {wishlist_id} not found")
        if wishlist.user_id != user_id:
            raise ForbiddenError("Cannot modify someone else's wishlist")
        removed = await self.uow.wishlists.remove_item(wishlist_id, item_id)
        if not removed:
            raise NotFoundError(f"Item {item_id} not in wishlist")

    # -------------------------------------------------------- share token
    async def generate_share_token(
        self, wishlist_id: uuid.UUID, user_id: uuid.UUID
    ) -> ShareTokenResponse:
        wishlist = await self.uow.wishlists.get_by_id(wishlist_id)
        if wishlist is None:
            raise NotFoundError(f"Wishlist {wishlist_id} not found")
        if wishlist.user_id != user_id:
            raise ForbiddenError("Cannot share someone else's wishlist")

        token = wishlist.share_token or secrets.token_urlsafe(20)[:32]
        await self.uow.wishlists.update(
            wishlist, share_token=token, is_public=True
        )
        return ShareTokenResponse(
            share_token=token,
            share_url=f"/shared/wishlists/{token}",
        )

    # ----------------------------------------------------------- helpers
    @staticmethod
    def _to_detail(
        wishlist: Wishlist, *, items: list[WishlistItem]
    ) -> WishlistDetail:
        share_url = (
            f"/shared/wishlists/{wishlist.share_token}"
            if wishlist.share_token
            else None
        )
        return WishlistDetail(
            id=wishlist.id,
            user_id=wishlist.user_id,
            name=wishlist.name,
            description=wishlist.description,
            is_public=wishlist.is_public,
            item_count=len(items),
            created_at=wishlist.created_at,
            updated_at=wishlist.updated_at,
            share_token=wishlist.share_token,
            share_url=share_url,
            items=[
                WishlistItemOut(
                    id=wi.id,
                    wishlist_id=wi.wishlist_id,
                    item_id=wi.item_id,
                    priority=wi.priority,
                    notes=wi.notes,
                    is_purchased=wi.is_purchased,
                    added_at=wi.added_at,
                    item=ItemSummary.model_validate(wi.item) if wi.item else None,
                )
                for wi in items
            ],
        )
