"""Unit tests for WishlistService."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.catalog import Item
from app.models.enums import ItemSource, ItemStatus
from app.models.user import Wishlist, WishlistItem
from app.repositories.wishlists import WishlistAlreadyContainsItem
from app.schemas.wishlists import AddToWishlistRequest, WishlistCreate, WishlistUpdate
from app.services.wishlist_service import WishlistService


# ---------------------------------------------------------------------------
# create_wishlist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_wishlist_creates_with_correct_user_id(uow, user_factory):
    user = await user_factory()
    service = WishlistService(uow)
    data = WishlistCreate(name="My Birthday List", is_public=False)
    detail = await service.create_wishlist(user.id, data)

    assert detail.user_id == user.id
    assert detail.name == "My Birthday List"
    assert detail.is_public is False


@pytest.mark.asyncio
async def test_create_wishlist_returns_empty_items_list(uow, user_factory):
    user = await user_factory()
    service = WishlistService(uow)
    detail = await service.create_wishlist(user.id, WishlistCreate(name="Gifts"))
    assert detail.items == []


# ---------------------------------------------------------------------------
# get_wishlist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_wishlist_private_raises_forbidden_for_other_user(
    uow, wishlist_factory
):
    wl = await wishlist_factory(is_public=False)
    other_user_id = uuid.uuid4()

    service = WishlistService(uow)
    with pytest.raises(ForbiddenError):
        await service.get_wishlist(wl.id, other_user_id)


@pytest.mark.asyncio
async def test_get_wishlist_public_allows_any_user(uow, wishlist_factory):
    wl = await wishlist_factory(is_public=True)
    other_user_id = uuid.uuid4()

    service = WishlistService(uow)
    result = await service.get_wishlist(wl.id, other_user_id)
    assert result.id == wl.id


@pytest.mark.asyncio
async def test_get_wishlist_raises_not_found_for_unknown_id(uow):
    service = WishlistService(uow)
    with pytest.raises(NotFoundError):
        await service.get_wishlist(uuid.uuid4(), None)


# ---------------------------------------------------------------------------
# add_item / remove_item
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_item_adds_to_wishlist(uow, wishlist_factory, item_factory, user_factory):
    user = await user_factory()
    wl = await wishlist_factory(user_id=user.id)
    item = await item_factory()

    service = WishlistService(uow)
    result = await service.add_item(
        wl.id, user.id, AddToWishlistRequest(item_id=item.id)
    )
    assert result.item_id == item.id
    assert result.wishlist_id == wl.id


@pytest.mark.asyncio
async def test_add_item_on_duplicate_raises_conflict_error(
    uow, wishlist_factory, item_factory, user_factory
):
    user = await user_factory()
    wl = await wishlist_factory(user_id=user.id)
    item = await item_factory()

    service = WishlistService(uow)
    await service.add_item(wl.id, user.id, AddToWishlistRequest(item_id=item.id))

    # Adding the same item again must raise ConflictError.
    with pytest.raises(ConflictError):
        await service.add_item(wl.id, user.id, AddToWishlistRequest(item_id=item.id))


@pytest.mark.asyncio
async def test_add_item_raises_forbidden_for_non_owner(
    uow, wishlist_factory, item_factory, user_factory
):
    owner = await user_factory()
    other = await user_factory()
    wl = await wishlist_factory(user_id=owner.id)
    item = await item_factory()

    service = WishlistService(uow)
    with pytest.raises(ForbiddenError):
        await service.add_item(wl.id, other.id, AddToWishlistRequest(item_id=item.id))


@pytest.mark.asyncio
async def test_add_item_raises_not_found_for_missing_item(
    uow, wishlist_factory, user_factory
):
    user = await user_factory()
    wl = await wishlist_factory(user_id=user.id)

    service = WishlistService(uow)
    with pytest.raises(NotFoundError):
        await service.add_item(
            wl.id, user.id, AddToWishlistRequest(item_id=uuid.uuid4())
        )


@pytest.mark.asyncio
async def test_remove_item_removes_from_wishlist(
    uow, wishlist_factory, item_factory, user_factory
):
    user = await user_factory()
    wl = await wishlist_factory(user_id=user.id)
    item = await item_factory()

    service = WishlistService(uow)
    await service.add_item(wl.id, user.id, AddToWishlistRequest(item_id=item.id))
    await service.remove_item(wl.id, user.id, item.id)

    # Verify it's gone by fetching items.
    detail = await service.get_wishlist(wl.id, user.id)
    assert not any(wi.item_id == item.id for wi in detail.items)


@pytest.mark.asyncio
async def test_remove_item_raises_not_found_when_item_not_in_wishlist(
    uow, wishlist_factory, item_factory, user_factory
):
    user = await user_factory()
    wl = await wishlist_factory(user_id=user.id)

    service = WishlistService(uow)
    with pytest.raises(NotFoundError):
        await service.remove_item(wl.id, user.id, uuid.uuid4())


# ---------------------------------------------------------------------------
# get_by_share_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_share_token_returns_public_wishlist(
    uow, wishlist_factory, async_session
):
    wl = await wishlist_factory(is_public=True)
    token = "sharetoken123"
    wl.share_token = token
    await async_session.flush()

    service = WishlistService(uow)
    result = await service.get_by_share_token(token)
    assert result.id == wl.id


@pytest.mark.asyncio
async def test_get_by_share_token_raises_not_found_for_nonexistent_token(uow):
    service = WishlistService(uow)
    with pytest.raises(NotFoundError):
        await service.get_by_share_token("doesnotexist")
