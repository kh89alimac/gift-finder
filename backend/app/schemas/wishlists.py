"""Wishlist schemas: CRUD + items + share token."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.items import ItemSummary


class WishlistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_public: bool = False


class WishlistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_public: bool | None = None


class AddToWishlistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: uuid.UUID
    priority: str = Field(default="normal", max_length=20)
    notes: str | None = Field(default=None, max_length=2000)


class WishlistItemOut(BaseModel):
    """One row from the join table, with the embedded item."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    wishlist_id: uuid.UUID
    item_id: uuid.UUID
    priority: str
    notes: str | None
    is_purchased: bool
    added_at: datetime
    item: ItemSummary | None = None


class WishlistSummary(BaseModel):
    """Summary view used in lists ('My Wishlists')."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    is_public: bool
    item_count: int = 0
    created_at: datetime
    updated_at: datetime


class WishlistDetail(WishlistSummary):
    """Detail view including the items array."""

    share_token: str | None = None
    share_url: str | None = None
    items: list[WishlistItemOut] = Field(default_factory=list)


class ShareTokenResponse(BaseModel):
    share_token: str
    share_url: str
