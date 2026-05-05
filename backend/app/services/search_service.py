"""Search service: full-text, vector, and AI-natural-language modes.

The AI flow:
1. Send the user's free-form query to OpenAI to extract structured filters
   (interests/occasion/recipient/budget) and a "cleaned" descriptive query.
2. Embed the cleaned query and run a vector search filtered by tag ids
   matching any extracted keyword.
3. If vector returns too few results, fall back to combining with full-text
   on the cleaned query.

We always return a single ranked list — clients shouldn't have to know which
mode produced which result.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select

from app.integrations.openai_client import (
    GiftFilterExtraction,
    embed_one,
    extract_gift_filters,
)
from app.models.catalog import Item
from app.models.taxonomy import Tag
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.items import RecipientProfile
from app.schemas.search import AISearchResponse, ExtractedFilters


class SearchService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ------------------------------------------------------------ text
    async def full_text_search(
        self,
        query: str,
        *,
        limit: int = 24,
        only_active: bool = True,
    ) -> list[Item]:
        return await self.uow.items.fulltext_search(
            query, limit=limit, only_active=only_active
        )

    # ------------------------------------------------------------- vector
    async def vector_search(
        self,
        query_text: str,
        *,
        limit: int = 24,
        tag_ids_filter: Sequence[int] | None = None,
    ) -> list[Item]:
        embedding = await embed_one(query_text)
        rows = await self.uow.items.vector_search(
            embedding,
            limit=limit,
            tag_ids_filter=tag_ids_filter,
        )
        return [item for item, _distance in rows]

    # ----------------------------------------------------- AI natural lang
    async def ai_natural_language_search(
        self,
        query: str,
        *,
        profile: RecipientProfile | None = None,
        limit: int = 24,
    ) -> AISearchResponse:
        """Hybrid: extract filters, vector-search, fall back to FTS if sparse."""
        # Run filter extraction *and* a speculative embedding of the raw
        # query in parallel — both are independent OpenAI calls, so doing
        # them concurrently roughly halves the LLM-bound latency. If the
        # cleaned query ends up materially different we re-embed; otherwise
        # we reuse the speculative result.
        extraction_result, raw_embedding_result = await asyncio.gather(
            extract_gift_filters(query),
            embed_one(query),
            return_exceptions=True,
        )

        # Filter extraction failure is unrecoverable — propagate it.
        if isinstance(extraction_result, BaseException):
            raise extraction_result
        extraction = extraction_result

        # Embedding failure is recoverable — fall back to FTS later.
        raw_embedding = (
            raw_embedding_result
            if not isinstance(raw_embedding_result, BaseException)
            else None
        )

        # Resolve any keyword to candidate tag ids.
        keyword_tag_ids = await self._resolve_keywords_to_tags(extraction)

        # Merge with any explicit ids from the recipient profile.
        all_tag_ids: list[int] = list(keyword_tag_ids)
        if profile:
            all_tag_ids.extend(profile.interest_tag_ids)
            all_tag_ids.extend(profile.occasion_tag_ids)
        all_tag_ids = list(dict.fromkeys(all_tag_ids))  # dedupe, keep order

        # Decide which query string to embed. Re-embed only if the cleaned
        # query differs materially (case/whitespace insensitive) — otherwise
        # reuse the speculative embedding we computed in parallel above.
        embedding_text = (extraction.cleaned_query or query).strip()
        items: list[Item]
        mode: str = "vector"
        try:
            if raw_embedding is None:
                raise RuntimeError("initial embedding failed")
            if embedding_text.lower() != query.lower().strip():
                embedding = await embed_one(embedding_text)
            else:
                embedding = raw_embedding
            rows = await self.uow.items.vector_search(
                embedding,
                limit=limit,
                tag_ids_filter=all_tag_ids or None,
            )
            items = [item for item, _ in rows]
        except Exception:
            items = []

        # If vector came back short or failed, augment with full-text.
        if len(items) < max(8, limit // 3):
            fts = await self.uow.items.fulltext_search(query, limit=limit)
            existing_ids = {i.id for i in items}
            for it in fts:
                if it.id not in existing_ids:
                    items.append(it)
                    existing_ids.add(it.id)
            mode = "hybrid"

        items = items[:limit]

        from app.schemas.items import ItemSummary

        return AISearchResponse(
            items=[ItemSummary.model_validate(i) for i in items],
            extracted=ExtractedFilters(
                interest_keywords=extraction.interest_keywords,
                occasion_keywords=extraction.occasion_keywords,
                recipient_keywords=extraction.recipient_keywords,
                price_min=Decimal(str(extraction.price_min)) if extraction.price_min else None,
                price_max=Decimal(str(extraction.price_max)) if extraction.price_max else None,
            ),
            mode=mode,  # type: ignore[arg-type]
        )

    # ---------------------------------------------------------- helpers
    async def _resolve_keywords_to_tags(
        self, extraction: GiftFilterExtraction
    ) -> list[int]:
        """Return tag ids whose name or slug matches any extracted keyword."""
        keywords = (
            extraction.interest_keywords
            + extraction.occasion_keywords
            + extraction.recipient_keywords
        )
        if not keywords:
            return []
        candidates = {k.lower().strip() for k in keywords if k.strip()}
        slug_candidates = {c.replace(" ", "-") for c in candidates}

        # Match on slug (exact, lowercase) OR case-insensitive name. We OR
        # several ``ilike`` expressions rather than using ``ilike_any`` because
        # the latter is dialect-specific and not always present.
        from sqlalchemy import or_

        name_predicates = [Tag.name.ilike(c) for c in candidates]
        stmt = select(Tag.id).where(
            or_(Tag.slug.in_(slug_candidates), *name_predicates)
        )
        result = await self.uow.session.execute(stmt)
        return list(result.scalars().all())
