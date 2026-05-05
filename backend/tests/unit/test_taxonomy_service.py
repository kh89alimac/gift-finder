"""Unit tests for TaxonomyService: merge_tags logic."""

from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.catalog import ItemTag
from app.services.taxonomy_service import TaxonomyService


# ---------------------------------------------------------------------------
# merge_tags
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_tags_migrates_item_tags_from_source_to_target(
    uow, tag_factory, item_factory, async_session
):
    source_tag = await tag_factory(slug="source-tag")
    target_tag = await tag_factory(slug="target-tag")
    item = await item_factory()

    # Tag the item with the source.
    async_session.add(ItemTag(item_id=item.id, tag_id=source_tag.id))
    await async_session.flush()

    service = TaxonomyService(uow)
    moved = await service.merge_tags(source_tag.id, target_tag.id)

    assert moved == 1

    # Verify the item is now tagged with target.
    from sqlalchemy import select
    result = await async_session.execute(
        select(ItemTag).where(
            ItemTag.item_id == item.id, ItemTag.tag_id == target_tag.id
        )
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_merge_tags_deletes_source_tag_after_migration(
    uow, tag_factory, item_factory, async_session
):
    from app.models.taxonomy import Tag

    source_tag = await tag_factory(slug="gone-tag")
    target_tag = await tag_factory(slug="remaining-tag")
    item = await item_factory()
    async_session.add(ItemTag(item_id=item.id, tag_id=source_tag.id))
    await async_session.flush()

    source_id = source_tag.id
    service = TaxonomyService(uow)
    await service.merge_tags(source_id, target_tag.id)

    deleted = await async_session.get(Tag, source_id)
    assert deleted is None


@pytest.mark.asyncio
async def test_merge_tags_handles_items_already_tagged_with_target(
    uow, tag_factory, item_factory, async_session
):
    """No duplicate item_tag rows should be created when the item is already
    tagged with the target."""
    source_tag = await tag_factory(slug="dup-source")
    target_tag = await tag_factory(slug="dup-target")
    item = await item_factory()

    # Tag item with BOTH source and target.
    async_session.add(ItemTag(item_id=item.id, tag_id=source_tag.id))
    async_session.add(ItemTag(item_id=item.id, tag_id=target_tag.id))
    await async_session.flush()

    service = TaxonomyService(uow)
    moved = await service.merge_tags(source_tag.id, target_tag.id)

    # The source row is a duplicate, so moved should be 0.
    assert moved == 0

    # Exactly one item_tag row for target must remain.
    from sqlalchemy import func, select
    result = await async_session.execute(
        select(func.count(ItemTag.item_id)).where(
            ItemTag.item_id == item.id,
            ItemTag.tag_id == target_tag.id,
        )
    )
    assert int(result.scalar_one()) == 1


@pytest.mark.asyncio
async def test_merge_tags_raises_validation_error_when_source_equals_target(
    uow, tag_factory
):
    tag = await tag_factory(slug="same-tag")
    service = TaxonomyService(uow)
    with pytest.raises(ValidationError, match="must differ"):
        await service.merge_tags(tag.id, tag.id)


@pytest.mark.asyncio
async def test_merge_tags_raises_not_found_when_tag_missing(uow, tag_factory):
    tag = await tag_factory(slug="existing-tag")
    service = TaxonomyService(uow)
    with pytest.raises(NotFoundError):
        await service.merge_tags(tag.id, 999999)  # nonexistent target


@pytest.mark.asyncio
async def test_merge_tags_zero_moved_when_source_has_no_items(
    uow, tag_factory
):
    source_tag = await tag_factory(slug="empty-source")
    target_tag = await tag_factory(slug="empty-target")
    service = TaxonomyService(uow)
    moved = await service.merge_tags(source_tag.id, target_tag.id)
    assert moved == 0
