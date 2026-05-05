"""Unit tests for ScraperOrchestrator."""

from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.base import ScrapeResult
from app.integrations.openai_client import CategorizationSuggestion
from app.models.enums import ItemSource, ItemStatus
from app.services.scraper_orchestrator import ScraperOrchestrator, _content_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scrape_result(**kwargs) -> ScrapeResult:
    defaults = {
        "title": "Cool Widget",
        "description": "A great product",
        "price": Decimal("49.99"),
        "currency": "USD",
        "image_url": "https://example.com/img.jpg",
        "product_url": "https://example.com/product",
        "brand": "BrandCo",
        "retailer": "Retailer Inc",
        "source_external_id": "ext-123",
        "source_url": "https://example.com/product",
    }
    defaults.update(kwargs)
    return ScrapeResult(**defaults)


# ---------------------------------------------------------------------------
# _content_hash helper
# ---------------------------------------------------------------------------


def test_content_hash_is_deterministic():
    result = _make_scrape_result()
    h1 = _content_hash(result)
    h2 = _content_hash(result)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_content_hash_differs_for_different_content():
    r1 = _make_scrape_result(title="Item A")
    r2 = _make_scrape_result(title="Item B")
    assert _content_hash(r1) != _content_hash(r2)


# ---------------------------------------------------------------------------
# auto_categorize
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_categorize_calls_openai_and_returns_suggestion(
    uow, mock_openai
):
    service = ScraperOrchestrator(uow)
    suggestion = await service.auto_categorize("Cool Tech Gadget", "A great device")

    assert isinstance(suggestion, CategorizationSuggestion)
    # The mock returns interest_slugs=["tech"]
    assert "tech" in suggestion.interest_slugs


@pytest.mark.asyncio
async def test_auto_categorize_empty_title_returns_empty_suggestion(uow, mocker):
    """Empty title triggers the early-exit guard in suggest_tags_for_item."""
    mocker.patch(
        "app.integrations.openai_client.suggest_tags_for_item",
        new_callable=AsyncMock,
        return_value=CategorizationSuggestion(),
    )
    service = ScraperOrchestrator(uow)
    suggestion = await service.auto_categorize("", None)
    assert suggestion.interest_slugs == []


# ---------------------------------------------------------------------------
# dedup via get_by_content_hash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dedup_item_returns_existing_item_for_known_hash(
    uow, item_factory, async_session
):
    item = await item_factory(title="Dup Item")
    content_hash = "abc123def456" + "0" * 52  # 64-char string
    item.content_hash = content_hash
    await async_session.flush()

    result = await uow.items.get_by_content_hash(content_hash)
    assert result is not None
    assert result.id == item.id


@pytest.mark.asyncio
async def test_dedup_item_returns_none_for_new_hash(uow):
    result = await uow.items.get_by_content_hash("brandnewhashthatdoesnotexist" + "0" * 37)
    assert result is None


# ---------------------------------------------------------------------------
# persist_scraped_batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_scraped_batch_bulk_upserts_items(
    uow, scraper_site_factory, mock_openai, async_session, mocker
):
    site = await scraper_site_factory()
    job_id = uuid.uuid4()

    results = [
        _make_scrape_result(title=f"Batch Item {i}", source_external_id=f"ext-{i}")
        for i in range(3)
    ]

    # Mock upsert_from_scrape to avoid pg-specific INSERT ON CONFLICT.
    fake_items = []
    for i, r in enumerate(results):
        fake_item = MagicMock()
        fake_item.id = uuid.uuid4()
        fake_item.title = r.title
        fake_items.append(fake_item)

    upsert_mock = AsyncMock(side_effect=[(fi, True) for fi in fake_items])
    uow.items.upsert_from_scrape = upsert_mock

    # Also stub get_by_content_hash to return None (all new).
    uow.items.get_by_content_hash = AsyncMock(return_value=None)

    # Mock session.add to avoid FK issues.
    original_add = async_session.add
    async_session.add = MagicMock()

    service = ScraperOrchestrator(uow)
    stats = await service.persist_scraped_batch(
        results, job_id=job_id, site_id=site.id, auto_categorize=False
    )

    async_session.add = original_add

    assert stats["found"] == 3
    assert stats["created"] == 3
    assert stats["skipped"] == 0


@pytest.mark.asyncio
async def test_persist_scraped_batch_skips_duplicate_content_hash(
    uow, scraper_site_factory, item_factory, mock_openai
):
    site = await scraper_site_factory()
    job_id = uuid.uuid4()

    r = _make_scrape_result(title="Dup Product")
    content_hash = _content_hash(r)
    existing = await item_factory(title="Dup Product")
    existing.content_hash = content_hash
    existing.source_site_id = site.id

    # Make get_by_content_hash return the existing item.
    uow.items.get_by_content_hash = AsyncMock(return_value=existing)

    service = ScraperOrchestrator(uow)
    stats = await service.persist_scraped_batch(
        [r], job_id=job_id, site_id=site.id, auto_categorize=False
    )

    assert stats["skipped"] == 1
    assert stats["created"] == 0
