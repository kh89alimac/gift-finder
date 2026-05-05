"""Admin review-queue schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ItemSource
from app.schemas.items import ItemSummary


class ReviewQueueFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: ItemSource | None = None
    assigned_to: uuid.UUID | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class ReviewQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    source: ItemSource
    priority: int
    assigned_to: uuid.UUID | None
    assigned_at: datetime | None
    created_at: datetime
    item: ItemSummary | None = None


class ItemApprovalPatch(BaseModel):
    """Strongly-typed patch payload applied when an admin approves an item.

    Listing every field explicitly stops a malicious client from setting
    arbitrary columns (status, role, embedding, …) via the approval flow.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    image_url: str | None = None
    product_url: str | None = None
    brand: str | None = None
    retailer: str | None = None


class ApproveRequest(BaseModel):
    """Optional fixup applied during approval (e.g. tweaking tags)."""

    model_config = ConfigDict(extra="forbid")

    item_patch: ItemApprovalPatch | None = None


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class BulkApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class BulkRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
