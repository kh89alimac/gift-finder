"""Scraper orchestrator service.

Coordinates the lifecycle of a single scrape:

1. Trigger — enqueue a ScraperJob for a site (or many sites).
2. Resolve — load the adapter class from the dotted path in the site config.
3. Persist — dedup + upsert results, route AI categorization to OpenAI.
4. Finalize — mark the job complete or failed and write counters.

The actual adapter execution lives in the Celery task; the orchestrator is
async + DB-only so it can be reused from tests, the API, and the worker.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.adapters.base import BaseScrapeAdapter, ScrapeResult
from app.adapters.registry import resolve_adapter
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.integrations.openai_client import (
    CategorizationSuggestion,
    suggest_tags_for_item,
)
from app.models.catalog import Item, ItemTag, ScraperSite
from app.models.enums import ItemSource, ItemStatus
from app.models.ingestion import ScraperJob
from app.models.taxonomy import Tag
from app.repositories.unit_of_work import UnitOfWork

log = get_logger(__name__)


class ScraperOrchestrator:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # -------------------------------------------------------- trigger
    async def trigger_site(
        self, site_id: int, *, priority: int = 5
    ) -> ScraperJob:
        """Enqueue a scrape job for the given site."""
        site = await self.uow.session.get(ScraperSite, site_id)
        if site is None:
            raise NotFoundError(f"ScraperSite {site_id} not found")
        if not site.is_active:
            raise ValidationError(f"ScraperSite {site_id} is inactive")

        job = await self.uow.scraper_jobs.create(
            site_id=site_id,
            priority=priority,
        )
        return job

    # ------------------------------------------------------ adapter
    def resolve_adapter(self, adapter_class_path: str) -> type[BaseScrapeAdapter]:
        try:
            return resolve_adapter(adapter_class_path)
        except KeyError as exc:
            raise ValidationError(f"Adapter not found: {adapter_class_path}") from exc

    async def get_site(self, site_id: int) -> ScraperSite:
        site = await self.uow.session.get(ScraperSite, site_id)
        if site is None:
            raise NotFoundError(f"ScraperSite {site_id} not found")
        return site

    # ----------------------------------------------------- categorize
    async def auto_categorize(
        self, title: str, description: str | None
    ) -> CategorizationSuggestion:
        """Use OpenAI function calling to suggest tag slugs."""
        return await suggest_tags_for_item(title, description)

    async def _resolve_tag_ids_from_slugs(self, slugs: Iterable[str]) -> list[int]:
        slugs = [s.strip().lower() for s in slugs if s and s.strip()]
        if not slugs:
            return []
        result = await self.uow.session.execute(
            select(Tag.id).where(Tag.slug.in_(slugs), Tag.is_active.is_(True))
        )
        return list(result.scalars().all())

    # ------------------------------------------------------ persist
    async def persist_scraped_batch(
        self,
        results: Iterable[ScrapeResult],
        *,
        job_id: uuid.UUID,
        site_id: int,
        auto_categorize: bool = True,
    ) -> dict[str, int]:
        """Dedupe, upsert, and tag a batch of scrape results.

        Returns counters: ``{found, created, updated, skipped}``. The caller
        is expected to ``commit`` the unit of work — we don't auto-commit
        here so the worker can decide to checkpoint mid-batch.
        """
        found = created = updated = skipped = 0

        for result in results:
            found += 1
            content_hash = _content_hash(result)
            existing = await self.uow.items.get_by_content_hash(content_hash)
            if existing and existing.source_site_id == site_id:
                # Truly identical content already on file — count it as a skip
                # to make duplicate detection visible in stats.
                skipped += 1
                continue

            data: dict[str, Any] = {
                "source": ItemSource.SCRAPER,
                "source_site_id": site_id,
                "source_external_id": result.source_external_id,
                "source_url": result.source_url or result.product_url,
                "title": result.title[:500],
                "description": result.description,
                "price": result.price,
                "currency": result.currency,
                "image_url": result.image_url,
                "product_url": result.product_url,
                "brand": result.brand,
                "retailer": result.retailer,
                "content_hash": content_hash,
                "status": ItemStatus.PENDING_REVIEW,
                "published_at": result.published_at or datetime.now(timezone.utc),
            }

            try:
                item, was_created = await self.uow.items.upsert_from_scrape(data)
            except Exception as exc:
                log.warning("scraper.persist.failed", error=str(exc), title=result.title)
                continue

            if was_created:
                created += 1
            else:
                updated += 1

            if auto_categorize and was_created:
                await self._apply_auto_categorization(item, result)

        return {
            "found": found,
            "created": created,
            "updated": updated,
            "skipped": skipped,
        }

    async def _apply_auto_categorization(self, item: Item, raw: ScrapeResult) -> None:
        suggestion = await self.auto_categorize(raw.title, raw.description)
        slugs = (
            suggestion.interest_slugs
            + suggestion.occasion_slugs
            + suggestion.recipient_slugs
        )
        tag_ids = await self._resolve_tag_ids_from_slugs(slugs)
        if not tag_ids:
            return
        for tid in tag_ids:
            self.uow.session.add(ItemTag(item_id=item.id, tag_id=tid))

    # -------------------------------------------------- job lifecycle
    async def mark_job_complete(
        self,
        job_id: uuid.UUID,
        *,
        items_found: int,
        items_created: int,
        items_updated: int,
        items_skipped: int,
    ) -> None:
        await self.uow.scraper_jobs.mark_completed(
            job_id,
            items_found=items_found,
            items_created=items_created,
            items_updated=items_updated,
            items_skipped=items_skipped,
        )

    async def mark_job_failed(
        self,
        job_id: uuid.UUID,
        *,
        error: str,
        will_retry: bool = False,
    ) -> None:
        await self.uow.scraper_jobs.mark_failed(
            job_id,
            error_message=error[:2000],
            will_retry=will_retry,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_hash(result: ScrapeResult) -> str:
    """Stable SHA-256 of the salient product fields. Used for dedup."""
    blob = "|".join(
        [
            result.title,
            result.description or "",
            str(result.price or ""),
            result.currency,
            result.image_url or "",
            result.product_url or "",
            result.brand or "",
        ]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
