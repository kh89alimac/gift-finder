"""Wishlist endpoints: CRUD, items, share-token sharing."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.dependencies import CurrentUser, OptionalUser, UowDep
from app.schemas.wishlists import (
    AddToWishlistRequest,
    ShareTokenResponse,
    WishlistCreate,
    WishlistDetail,
    WishlistItemOut,
    WishlistSummary,
    WishlistUpdate,
)
from app.services.wishlist_service import WishlistService

router = APIRouter(prefix="/wishlists", tags=["wishlists"])


@router.get("", response_model=list[WishlistSummary])
async def list_wishlists(
    uow: UowDep, current_user: CurrentUser
) -> list[WishlistSummary]:
    service = WishlistService(uow)
    return await service.list_for_user(current_user.id)


@router.post("", response_model=WishlistDetail, status_code=status.HTTP_201_CREATED)
async def create_wishlist(
    payload: WishlistCreate,
    uow: UowDep,
    current_user: CurrentUser,
) -> WishlistDetail:
    service = WishlistService(uow)
    return await service.create_wishlist(current_user.id, payload)


@router.get("/{wishlist_id}", response_model=WishlistDetail)
async def get_wishlist(
    wishlist_id: uuid.UUID,
    uow: UowDep,
    current_user: OptionalUser,
) -> WishlistDetail:
    service = WishlistService(uow)
    return await service.get_wishlist(
        wishlist_id, current_user.id if current_user else None
    )


@router.patch("/{wishlist_id}", response_model=WishlistDetail)
async def update_wishlist(
    wishlist_id: uuid.UUID,
    payload: WishlistUpdate,
    uow: UowDep,
    current_user: CurrentUser,
) -> WishlistDetail:
    service = WishlistService(uow)
    return await service.update_wishlist(wishlist_id, current_user.id, payload)


@router.delete("/{wishlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wishlist(
    wishlist_id: uuid.UUID,
    uow: UowDep,
    current_user: CurrentUser,
) -> None:
    service = WishlistService(uow)
    await service.delete_wishlist(wishlist_id, current_user.id)


# --------------------------------------------------------------------- items


@router.post(
    "/{wishlist_id}/items",
    response_model=WishlistItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_wishlist(
    wishlist_id: uuid.UUID,
    payload: AddToWishlistRequest,
    uow: UowDep,
    current_user: CurrentUser,
) -> WishlistItemOut:
    service = WishlistService(uow)
    return await service.add_item(wishlist_id, current_user.id, payload)


@router.delete(
    "/{wishlist_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_from_wishlist(
    wishlist_id: uuid.UUID,
    item_id: uuid.UUID,
    uow: UowDep,
    current_user: CurrentUser,
) -> None:
    service = WishlistService(uow)
    await service.remove_item(wishlist_id, current_user.id, item_id)


# -------------------------------------------------------------- share token


@router.post("/{wishlist_id}/share", response_model=ShareTokenResponse)
async def generate_share_token(
    wishlist_id: uuid.UUID,
    uow: UowDep,
    current_user: CurrentUser,
) -> ShareTokenResponse:
    service = WishlistService(uow)
    return await service.generate_share_token(wishlist_id, current_user.id)


@router.get("/shared/{token}", response_model=WishlistDetail)
async def get_shared_wishlist(token: str, uow: UowDep) -> WishlistDetail:
    service = WishlistService(uow)
    return await service.get_by_share_token(token)
