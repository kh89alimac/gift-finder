"""Item schemas: discovery feed payloads, detail view, manual entry input."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.enums import InteractionType, ItemSource, ItemStatus
from app.schemas.taxonomy import TagSlim


class ItemSummary(BaseModel):
    """Lean item shape for grids and lists.

    Excludes description/embedding to keep the discovery payload small.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    price: Decimal | None
    currency: str
    image_url: str | None
    product_url: str | None
    brand: str | None
    retailer: str | None
    source: ItemSource
    status: ItemStatus
    tags: list[TagSlim] = Field(default_factory=list)
    published_at: datetime | None
    created_at: datetime


class ItemDetail(ItemSummary):
    """Full item view including description, counters, and provenance."""

    description: str | None
    source_site_id: int | None
    source_external_id: str | None
    source_url: str | None
    view_count: int
    save_count: int
    click_count: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Discovery filters
# ---------------------------------------------------------------------------


class RecipientProfile(BaseModel):
    """Optional caller-supplied gift recipient profile.

    Used by recommendation + AI search to bias results. Everything is
    optional — the UI nudges users to fill it out for better results but does
    not require it.
    """

    model_config = ConfigDict(extra="forbid")

    age_range: str | None = Field(default=None, description="e.g. '25-34'")
    relationship: str | None = Field(default=None, description="e.g. 'spouse', 'colleague'")
    interest_tag_ids: list[int] = Field(default_factory=list, max_length=20)
    occasion_tag_ids: list[int] = Field(default_factory=list, max_length=10)
    budget_min: Decimal | None = Field(default=None, ge=0)
    budget_max: Decimal | None = Field(default=None, ge=0)

    @field_validator("budget_max")
    @classmethod
    def _budget_order(cls, v: Decimal | None, info: object) -> Decimal | None:
        # Validators only see siblings already validated — relax check.
        return v


class DiscoveryFilters(BaseModel):
    """Query-string filters for ``GET /items``."""

    model_config = ConfigDict(extra="forbid")

    tag_ids: list[int] = Field(default_factory=list, max_length=50)
    require_all_tags: bool = False
    price_min: Decimal | None = Field(default=None, ge=0)
    price_max: Decimal | None = Field(default=None, ge=0)
    sort: str = Field(default="relevance")
    cursor: str | None = None
    page_size: int = Field(default=24, ge=1, le=100)


# ---------------------------------------------------------------------------
# Manual entry
# ---------------------------------------------------------------------------


class ItemManualIn(BaseModel):
    """Admin-supplied payload to create an item by hand."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    image_url: HttpUrl | None = None
    product_url: HttpUrl | None = None
    brand: str | None = Field(default=None, max_length=200)
    retailer: str | None = Field(default=None, max_length=200)
    tag_ids: list[int] = Field(default_factory=list)
    publish: bool = Field(
        default=False,
        description="When true the item is created with status=active, otherwise pending_review",
    )

    @field_validator("currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class ItemManualUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    image_url: HttpUrl | None = None
    product_url: HttpUrl | None = None
    brand: str | None = Field(default=None, max_length=200)
    retailer: str | None = Field(default=None, max_length=200)
    tag_ids: list[int] | None = None
    status: ItemStatus | None = None


class ItemStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ItemStatus
    rejection_reason: str | None = None


class InteractionRecord(BaseModel):
    """Body for ``POST /items/{id}/interactions``."""

    model_config = ConfigDict(extra="forbid")

    interaction_type: InteractionType
