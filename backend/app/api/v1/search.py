"""Search endpoints: text/vector + AI natural-language."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from app.dependencies import OptionalUser, UowDep
from app.schemas.items import ItemSummary
from app.schemas.search import AISearchRequest, AISearchResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[ItemSummary])
async def search(
    uow: UowDep,
    _user: OptionalUser,
    q: str = Query(min_length=1, max_length=300),
    mode: Literal["text", "vector"] = "text",
    limit: int = Query(default=24, ge=1, le=50),
) -> list[ItemSummary]:
    """Quick-search endpoint. ``mode=text`` uses tsvector; ``vector`` uses embeddings."""
    service = SearchService(uow)
    if mode == "text":
        items = await service.full_text_search(q, limit=limit)
    else:
        items = await service.vector_search(q, limit=limit)
    return [ItemSummary.model_validate(i) for i in items]


@router.post("/ai", response_model=AISearchResponse)
async def ai_search(
    payload: AISearchRequest,
    uow: UowDep,
    _user: OptionalUser,
) -> AISearchResponse:
    """Natural-language gift search powered by OpenAI function calling."""
    service = SearchService(uow)
    return await service.ai_natural_language_search(
        payload.query,
        profile=payload.profile,
        limit=payload.limit,
    )
