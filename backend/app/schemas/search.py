"""Search request/response schemas."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.items import ItemSummary, RecipientProfile


class SearchFilters(BaseModel):
    """Common filters shared by text + AI search."""

    model_config = ConfigDict(extra="forbid")

    tag_ids: list[int] = Field(default_factory=list, max_length=50)
    price_min: Decimal | None = Field(default=None, ge=0)
    price_max: Decimal | None = Field(default=None, ge=0)


class AISearchRequest(BaseModel):
    """Natural-language gift query plus optional recipient context."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=500)
    profile: RecipientProfile | None = None
    limit: int = Field(default=24, ge=1, le=50)


class ExtractedFilters(BaseModel):
    """Filters that the LLM pulled out of the natural-language query.

    Surfaced to the client so the UI can show "we're searching for X under
    $Y for occasion Z" — gives the user a chance to correct a misread.
    """

    interest_keywords: list[str] = Field(default_factory=list)
    occasion_keywords: list[str] = Field(default_factory=list)
    recipient_keywords: list[str] = Field(default_factory=list)
    price_min: Decimal | None = None
    price_max: Decimal | None = None


class AISearchResponse(BaseModel):
    items: list[ItemSummary]
    extracted: ExtractedFilters
    mode: Literal["vector", "hybrid", "fulltext"] = "hybrid"
