"""Recommendation service.

Two flavors:

* **Personalized** — built from the user's per-tag signals. We pick their top
  tags and run :meth:`ItemRepository.search_by_profile` against them.
* **Cold start** — when a user has no signals yet (brand new account, or
  anonymous), we serve the trending feed: most-saved items in the last 30
  days, falling back to most recent.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.logging import get_logger
from app.core.redis import get_redis
from app.integrations.openai_client import embed_one
from app.models.catalog import Item
from app.models.enums import ItemStatus
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.items import ItemSummary, RecipientProfile
from app.schemas.recommendations import RecommendationItem, RecommendationResponse

log = get_logger(__name__)

CACHE_TTL_SECONDS = 5 * 60  # 5 minutes; bump if recs are expensive


class RecommendationService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ------------------------------------------------------- public api
    async def get_recommendations(
        self,
        user_id: uuid.UUID | None,
        profile: RecipientProfile | None = None,
        *,
        page_size: int = 24,
    ) -> RecommendationResponse:
        """Return cached recs if fresh, otherwise compute + cache."""
        cache_key = self._cache_key(user_id, profile, page_size)
        redis = get_redis()
        cached = await redis.get(cache_key)
        if cached:
            try:
                payload = json.loads(cached)
                return RecommendationResponse.model_validate(payload)
            except Exception:  # malformed cache — recompute
                log.warning("recs.cache.invalid", key=cache_key)

        result = await self._compute(user_id, profile, page_size)
        await redis.setex(cache_key, CACHE_TTL_SECONDS, result.model_dump_json())
        return result

    async def compute_for_user(self, user_id: uuid.UUID) -> RecommendationResponse:
        """Force-recompute and overwrite cache. Called by the worker task."""
        result = await self._compute(user_id, None, page_size=24)
        cache_key = self._cache_key(user_id, None, 24)
        await get_redis().setex(cache_key, CACHE_TTL_SECONDS, result.model_dump_json())
        return result

    async def get_similar_items(
        self, item_id: uuid.UUID, *, n: int = 5
    ) -> list[ItemSummary]:
        """Vector-nearest neighbors of the source item, excluding itself."""
        item = await self.uow.items.get_by_id(item_id)
        if item is None or item.embedding is None:
            return []

        rows = await self.uow.items.vector_search(
            item.embedding, limit=n + 1
        )
        out: list[ItemSummary] = []
        for it, _dist in rows:
            if it.id == item_id:
                continue
            out.append(ItemSummary.model_validate(it))
            if len(out) >= n:
                break
        return out

    # ------------------------------------------------------- internals
    async def _compute(
        self,
        user_id: uuid.UUID | None,
        profile: RecipientProfile | None,
        page_size: int,
    ) -> RecommendationResponse:
        is_personalized = False
        items: list[Item] = []

        # Source 1: explicit profile
        profile_tag_ids: list[int] = []
        if profile:
            profile_tag_ids = list(profile.interest_tag_ids) + list(profile.occasion_tag_ids)

        # Source 2: signals from interactions
        signal_tag_ids: list[int] = []
        if user_id is not None:
            top = await self.uow.recommendations.top_tags_for_user(user_id, limit=15)
            from decimal import Decimal as _D

            signal_tag_ids = [t.id for t, _score in top if _score > _D("0")]

        tag_ids = list(dict.fromkeys(signal_tag_ids + profile_tag_ids))

        if tag_ids:
            is_personalized = True
            items = await self.uow.items.search_by_profile(
                tag_ids=tag_ids,
                price_min=profile.budget_min if profile else None,
                price_max=profile.budget_max if profile else None,
                limit=page_size,
            )

        # Cold start fallback — trending or most recent active.
        if not items:
            items = await self._trending(limit=page_size)

        rec_items = [
            RecommendationItem(
                item=ItemSummary.model_validate(i),
                score=1.0,  # the ranker is implicit in the SQL ordering
            )
            for i in items
        ]
        return RecommendationResponse(
            items=rec_items,
            is_personalized=is_personalized,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _trending(self, *, limit: int) -> list[Item]:
        # Most saved items, falling back to most recently published if all
        # rows have zero saves (brand new install).
        stmt = (
            select(Item)
            .where(Item.status == ItemStatus.ACTIVE)
            .order_by(Item.save_count.desc(), Item.published_at.desc().nulls_last())
            .limit(limit)
        )
        result = await self.uow.session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _cache_key(
        user_id: uuid.UUID | None,
        profile: RecipientProfile | None,
        page_size: int,
    ) -> str:
        u = str(user_id) if user_id else "anon"
        p = profile.model_dump_json() if profile else "none"
        # Stable hash so the same profile always hits the same key.
        import hashlib

        h = hashlib.sha1(f"{u}:{p}:{page_size}".encode()).hexdigest()[:12]
        return f"recs:{u}:{h}"
