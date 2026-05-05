"""Unit tests for ItemService.

All persistence is provided via the ``uow`` fixture (in-memory SQLite, rolled
back after each test). No real external services are called.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.models.catalog import Item, ItemTag
from app.models.enums import InteractionType, ItemSource, ItemStatus
from app.models.user import User, UserInteraction
from app.schemas.items import DiscoveryFilters
from app.services.item_service import ItemService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _count_interactions(session, user_id, item_id) -> int:
    from sqlalchemy import func, select

    result = await session.execute(
        select(func.count(UserInteraction.id)).where(
            UserInteraction.user_id == user_id,
            UserInteraction.item_id == item_id,
        )
    )
    return int(result.scalar_one())


# ---------------------------------------------------------------------------
# list_items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_items_with_no_filters_returns_paginated_results(
    uow, item_factory
):
    """Basic pagination: create 3 active items, expect all 3 back."""
    for i in range(3):
        await item_factory(title=f"Active Item {i}", status=ItemStatus.ACTIVE)

    service = ItemService(uow)
    page = await service.list_items(DiscoveryFilters())
    assert len(page.items) >= 3


@pytest.mark.asyncio
async def test_list_items_with_budget_filter_applies_price_range(
    uow, item_factory
):
    """Only items inside [price_min, price_max] should come back."""
    await item_factory(title="Cheap Item", price=Decimal("5.00"))
    await item_factory(title="Mid Item", price=Decimal("25.00"))
    await item_factory(title="Expensive Item", price=Decimal("200.00"))

    service = ItemService(uow)
    page = await service.list_items(
        DiscoveryFilters(price_min=Decimal("10.00"), price_max=Decimal("50.00"))
    )
    titles = {i.title for i in page.items}
    assert "Mid Item" in titles
    assert "Cheap Item" not in titles
    assert "Expensive Item" not in titles


@pytest.mark.asyncio
async def test_list_items_with_tag_filter_applies_intersection(
    uow, item_factory, tag_factory, async_session
):
    """Items tagged with the requested tag_id are returned; others are excluded."""
    tag = await tag_factory(slug="birthday")
    item_with_tag = await item_factory(title="Birthday Gift")
    item_without = await item_factory(title="Generic Gift")

    async_session.add(ItemTag(item_id=item_with_tag.id, tag_id=tag.id))
    await async_session.flush()

    service = ItemService(uow)
    page = await service.list_items(DiscoveryFilters(tag_ids=[tag.id]))
    ids = {i.id for i in page.items}
    assert item_with_tag.id in ids
    assert item_without.id not in ids


@pytest.mark.asyncio
async def test_list_items_excludes_non_active_items(uow, item_factory):
    """Items in PENDING_REVIEW / REJECTED / ARCHIVED must not appear."""
    await item_factory(title="Pending", status=ItemStatus.PENDING_REVIEW)
    await item_factory(title="Rejected", status=ItemStatus.REJECTED)
    await item_factory(title="Active", status=ItemStatus.ACTIVE)

    service = ItemService(uow)
    page = await service.list_items(DiscoveryFilters())
    titles = {i.title for i in page.items}
    assert "Pending" not in titles
    assert "Rejected" not in titles
    assert "Active" in titles


# ---------------------------------------------------------------------------
# get_item_detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_item_detail_returns_item(uow, item_factory):
    item = await item_factory(title="Detail Item")
    service = ItemService(uow)
    result = await service.get_item_detail(item.id)
    assert result.id == item.id
    assert result.title == "Detail Item"


@pytest.mark.asyncio
async def test_get_item_detail_raises_not_found_for_unknown_id(uow):
    service = ItemService(uow)
    with pytest.raises(NotFoundError):
        await service.get_item_detail(uuid.uuid4())


@pytest.mark.asyncio
async def test_get_item_detail_returns_item_with_tags(
    uow, item_factory, tag_factory, async_session
):
    tag = await tag_factory(slug="art")
    item = await item_factory(title="Art Gift")
    async_session.add(ItemTag(item_id=item.id, tag_id=tag.id))
    await async_session.flush()

    service = ItemService(uow)
    result = await service.get_item_detail(item.id)
    tag_slugs = [t.slug for t in result.tags]
    assert "art" in tag_slugs


# ---------------------------------------------------------------------------
# record_interaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_interaction_creates_user_interaction_row(
    uow, item_factory, user_factory, async_session
):
    user = await user_factory()
    item = await item_factory()

    # Stub out the recommendation upsert to avoid pgvector/complex query issues.
    with patch.object(
        uow.recommendations, "upsert_signals_bulk", new_callable=AsyncMock
    ):
        service = ItemService(uow)
        await service.record_interaction(user.id, item.id, InteractionType.VIEW)
        await async_session.flush()

    count = await _count_interactions(async_session, user.id, item.id)
    assert count == 1


@pytest.mark.asyncio
async def test_record_interaction_raises_not_found_for_unknown_item(
    uow, user_factory
):
    user = await user_factory()
    service = ItemService(uow)
    with pytest.raises(NotFoundError):
        await service.record_interaction(user.id, uuid.uuid4(), InteractionType.VIEW)


@pytest.mark.asyncio
async def test_record_interaction_increments_view_count(
    uow, item_factory, user_factory, async_session
):
    user = await user_factory()
    item = await item_factory()
    original_view_count = item.view_count

    with patch.object(
        uow.recommendations, "upsert_signals_bulk", new_callable=AsyncMock
    ):
        service = ItemService(uow)
        await service.record_interaction(user.id, item.id, InteractionType.VIEW)
        await async_session.flush()

    # Reload to see updated counter.
    await async_session.refresh(item)
    assert item.view_count == original_view_count + 1
