"""Recommendation endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.dependencies import CurrentUser, OptionalUser, UowDep
from app.schemas.items import ItemSummary, RecipientProfile
from app.schemas.recommendations import RecommendationResponse
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationResponse)
async def get_recommendations(
    uow: UowDep,
    user: OptionalUser,
    page_size: int = Query(default=24, ge=1, le=50),
) -> RecommendationResponse:
    """Personalized recs for authed users; trending feed for anonymous."""
    service = RecommendationService(uow)
    return await service.get_recommendations(
        user.id if user else None,
        profile=None,
        page_size=page_size,
    )


@router.post("/refresh", response_model=RecommendationResponse)
async def refresh_recommendations(
    uow: UowDep,
    current_user: CurrentUser,
) -> RecommendationResponse:
    """Force a recompute of the caller's recs."""
    service = RecommendationService(uow)
    return await service.compute_for_user(current_user.id)


@router.post("/profile", response_model=RecommendationResponse)
async def get_recommendations_for_profile(
    profile: RecipientProfile,
    uow: UowDep,
    user: OptionalUser,
    page_size: int = Query(default=24, ge=1, le=50),
) -> RecommendationResponse:
    """Recs biased by an explicit recipient profile (gift-giver flow)."""
    service = RecommendationService(uow)
    return await service.get_recommendations(
        user.id if user else None,
        profile=profile,
        page_size=page_size,
    )


@router.get("/similar/{item_id}", response_model=list[ItemSummary])
async def similar_items(
    item_id: uuid.UUID,
    uow: UowDep,
    n: int = Query(default=5, ge=1, le=20),
) -> list[ItemSummary]:
    service = RecommendationService(uow)
    return await service.get_similar_items(item_id, n=n)
