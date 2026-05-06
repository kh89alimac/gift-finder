"""Public item endpoints: discovery feed, detail view, taxonomy slices."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Query, status

from app.dependencies import CurrentUser, OptionalUser, UowDep
from app.schemas.common import CursorPage
from app.schemas.items import (
    DiscoveryFilters,
    InteractionRecord,
    ItemDetail,
    ItemSummary,
)
from app.schemas.taxonomy import TagOut
from app.services.item_service import ItemService

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=CursorPage[ItemSummary])
async def list_items(
    uow: UowDep,
    _user: OptionalUser,
    tag_ids: list[int] = Query(default_factory=list),
    require_all_tags: bool = False,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    sort: str = Query(default="relevance"),
    cursor: str | None = None,
    page_size: int = Query(default=24, ge=1, le=100),
) -> CursorPage[ItemSummary]:
    """Paginated discovery feed of active items."""
    filters = DiscoveryFilters(
        tag_ids=tag_ids,
        require_all_tags=require_all_tags,
        price_min=price_min,
        price_max=price_max,
        sort=sort,
        cursor=cursor,
        page_size=page_size,
    )
    service = ItemService(uow)
    return await service.list_items(filters)


@router.get("/categories", response_model=list[TagOut])
async def list_categories(uow: UowDep) -> list[TagOut]:
    """Active 'category' tags for the discovery sidebar."""
    tags = await uow.tags.get_by_type("category")
    return [TagOut.model_validate(t) for t in tags]


@router.get("/occasions", response_model=list[TagOut])
async def list_occasions(uow: UowDep) -> list[TagOut]:
    """Active 'occasion' tags."""
    tags = await uow.tags.get_by_type("occasion")
    return [TagOut.model_validate(t) for t in tags]


@router.get("/{item_id}", response_model=ItemDetail)
async def get_item(
    item_id: uuid.UUID,
    uow: UowDep,
    _user: OptionalUser,
) -> ItemDetail:
    service = ItemService(uow)
    item = await service.get_item_detail(item_id)
    return ItemDetail.model_validate(item)


@router.post(
    "/{item_id}/interactions",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def record_interaction(
    item_id: uuid.UUID,
    payload: InteractionRecord,
    uow: UowDep,
    current_user: CurrentUser,
) -> None:
    """Record a view/click/save/etc. for the current user."""
    service = ItemService(uow)
    await service.record_interaction(
        current_user.id, item_id, payload.interaction_type
    )
