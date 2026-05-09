"""Item service: discovery feed, detail view, status updates, interactions."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.core.exceptions import NotFoundError
from app.models.catalog import Item, ItemTag
from app.models.enums import InteractionType, ItemStatus
from app.models.user import UserInteraction
from app.repositories.items import ItemPageCursor
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.common import CursorPage, decode_cursor, encode_cursor
from app.schemas.items import DiscoveryFilters, ItemSummary

# Score deltas applied to recommendation_signals per interaction type.
# Positive when the user shows interest, zero/negative when they don't.
_INTERACTION_WEIGHTS: dict[InteractionType, float] = {
    InteractionType.VIEW: 0.1,
    InteractionType.CLICK: 0.5,
    InteractionType.SAVE: 1.0,
    InteractionType.SHARE: 1.0,
    InteractionType.PURCHASE: 2.0,
    InteractionType.REMOVE: -0.5,
    InteractionType.DISMISS: -0.3,
}


class ItemService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ------------------------------------------------------------- listing
    async def list_items(
        self, filters: DiscoveryFilters
    ) -> CursorPage[ItemSummary]:
        """Discovery feed with cursor pagination and tag/price filters."""
        cursor_obj: ItemPageCursor | None = None
        if filters.cursor:
            try:
                payload = decode_cursor(filters.cursor)
                cursor_obj = ItemPageCursor(
                    published_at=(
                        None
                        if payload.get("published_at") is None
                        else _parse_iso(payload["published_at"])
                    ),
                    id=uuid.UUID(payload["id"]),
                )
            except (ValueError, KeyError):
                cursor_obj = None

        items = await self.uow.items.search_by_profile(
            tag_ids=filters.tag_ids or None,
            price_min=filters.price_min,
            price_max=filters.price_max,
            sort=filters.sort,
            limit=filters.page_size + 1,  # fetch one extra to compute next_cursor
            cursor=cursor_obj,
            require_all_tags=filters.require_all_tags,
        )

        next_cursor: str | None = None
        if len(items) > filters.page_size:
            tail = items[filters.page_size - 1]
            items = items[: filters.page_size]
            next_cursor = encode_cursor(
                {
                    "published_at": (
                        tail.published_at.isoformat() if tail.published_at else None
                    ),
                    "id": str(tail.id),
                }
            )

        return CursorPage[ItemSummary](
            items=[ItemSummary.model_validate(i) for i in items],
            next_cursor=next_cursor,
        )

    # -------------------------------------------------------------- detail
    async def get_item_detail(self, item_id: uuid.UUID) -> Item:
        item = await self.uow.items.get_by_id(item_id)
        if item is None:
            raise NotFoundError(f"Item {item_id} not found")
        return item

    # ------------------------------------------------------------- status
    async def update_item_status(
        self,
        item_id: uuid.UUID,
        status: ItemStatus,
        *,
        reviewer_id: uuid.UUID | None = None,
        rejection_reason: str | None = None,
    ) -> Item:
        item = await self.uow.items.get_by_id(item_id)
        if item is None:
            raise NotFoundError(f"Item {item_id} not found")
        await self.uow.items.update(
            item,
            status=status,
            reviewed_by=reviewer_id,
            rejection_reason=rejection_reason if status == ItemStatus.REJECTED else None,
        )
        return item

    # -------------------------------------------------------- interactions
    async def record_interaction(
        self,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
        interaction_type: InteractionType,
    ) -> None:
        """Persist a UserInteraction row, bump counters, and update signals.

        We keep the implementation in a single UoW so all three writes commit
        together — there's no point recording an interaction whose recs
        signal failed to update.
        """
        item = await self.uow.items.get_by_id(item_id)
        if item is None:
            raise NotFoundError(f"Item {item_id} not found")

        # Persist the raw event.
        self.uow.session.add(
            UserInteraction(
                user_id=user_id,
                item_id=item_id,
                interaction_type=interaction_type,
            )
        )

        # Bump the appropriate counter on the item.
        counter_map = {
            InteractionType.VIEW: "view_count",
            InteractionType.CLICK: "click_count",
            InteractionType.SAVE: "save_count",
        }
        if (counter := counter_map.get(interaction_type)) is not None:
            await self.uow.items.increment_counter(item_id, counter)

        # Update recommendation signals for every tag attached to the item.
        weight = _INTERACTION_WEIGHTS.get(interaction_type, 0.0)
        if weight != 0.0:
            tag_ids = await self._tag_ids_for_item(item_id)
            from decimal import Decimal as _D  # local to avoid global import cost
            if tag_ids:
                pairs = [(tid, _D(str(weight))) for tid in tag_ids]
                await self.uow.recommendations.upsert_signals_bulk(user_id, pairs)

    async def _tag_ids_for_item(self, item_id: uuid.UUID) -> list[int]:
        result = await self.uow.session.execute(
            select(ItemTag.tag_id).where(ItemTag.item_id == item_id)
        )
        return [row for row in result.scalars().all()]

    # --------------------------------------------------------- moderation
    async def list_pending_review(self, *, limit: int = 50) -> list[Item]:
        return await self.uow.items.list_pending_review(limit=limit)

    async def total_active(self) -> int:
        result = await self.uow.session.execute(
            select(func.count()).select_from(Item).where(Item.status == ItemStatus.ACTIVE)
        )
        return int(result.scalar_one())


def _parse_iso(value: str) -> "datetime":  # noqa: F821 - hint string for forward ref
    from datetime import datetime as _dt

    return _dt.fromisoformat(value)
