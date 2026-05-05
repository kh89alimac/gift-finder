"""Ingestion-side schemas: scraper jobs, IG queue, manual entry, CSV import."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.enums import InstagramQueueStatus, JobStatus


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


class ScraperTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_id: int = Field(ge=1)
    priority: int = Field(default=5, ge=1, le=10)


class ScraperJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: int | None
    schedule_id: int | None
    status: JobStatus
    priority: int
    items_found: int
    items_created: int
    items_updated: int
    items_skipped: int
    error_message: str | None
    retry_count: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Instagram
# ---------------------------------------------------------------------------


class InstagramTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(
        description="Instagram user id or hashtag id depending on target_type"
    )
    target_type: Literal["user", "hashtag"]
    limit: int = Field(default=25, ge=1, le=100)


class InstagramQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instagram_post_id: str
    permalink: str
    image_url: str
    caption: str | None
    account_handle: str
    hashtags: list[str]
    suggested_tags: dict[str, Any]
    confidence_score: Decimal
    status: InstagramQueueStatus
    promoted_item_id: uuid.UUID | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------


class CsvImportRowError(BaseModel):
    row_number: int = Field(ge=1)
    errors: list[str]


class CsvImportResult(BaseModel):
    total_rows: int
    inserted: int
    updated: int
    skipped: int
    errors: list[CsvImportRowError] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Image upload response
# ---------------------------------------------------------------------------


class ImageUploadResponse(BaseModel):
    item_id: uuid.UUID
    image_url: HttpUrl | str
    image_s3_key: str
