"""Recommendation schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.items import ItemSummary


class RecommendationItem(BaseModel):
    item: ItemSummary
    score: float = Field(ge=0)
    reason: str | None = None


class RecommendationResponse(BaseModel):
    """List of personalized recommendations.

    ``generated_at`` lets clients tell when they should ask for fresh recs;
    we cache for short windows to avoid recomputing on every page load.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[RecommendationItem]
    is_personalized: bool = Field(
        description="False when the result is the cold-start trending feed",
    )
    generated_at: str
