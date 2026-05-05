"""Unit tests for ReviewQueueService."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import NotFoundError
from app.models.admin import ReviewQueue
from app.models.enums import ItemSource, ItemStatus
from app.services.review_queue_service import ReviewQueueService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_queue_entry(
    async_session, item, source: ItemSource = ItemSource.MANUAL
) -> ReviewQueue:
    entry = ReviewQueue(item_id=item.id, source=source, priority=5)
    async_session.add(entry)
    await async_session.flush()
    return entry


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_sets_item_status_to_active(
    uow, item_factory, user_factory, async_session
):
    admin = await user_factory()
    item = await item_factory(status=ItemStatus.PENDING_REVIEW)
    queue_entry = await _create_queue_entry(async_session, item)

    service = ReviewQueueService(uow)
    updated_item = await service.approve(queue_entry.id, admin.id)

    await async_session.refresh(updated_item)
    assert updated_item.status == ItemStatus.ACTIVE
    assert updated_item.reviewed_by == admin.id


@pytest.mark.asyncio
async def test_approve_removes_queue_entry(
    uow, item_factory, user_factory, async_session
):
    admin = await user_factory()
    item = await item_factory(status=ItemStatus.PENDING_REVIEW)
    entry = await _create_queue_entry(async_session, item)
    entry_id = entry.id

    service = ReviewQueueService(uow)
    await service.approve(entry_id, admin.id)

    # The entry should be gone.
    refreshed = await async_session.get(ReviewQueue, entry_id)
    assert refreshed is None


@pytest.mark.asyncio
async def test_approve_raises_not_found_for_unknown_queue_id(
    uow, user_factory
):
    admin = await user_factory()
    service = ReviewQueueService(uow)
    with pytest.raises(NotFoundError):
        await service.approve(uuid.uuid4(), admin.id)


# ---------------------------------------------------------------------------
# reject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_sets_item_status_to_rejected_with_reason(
    uow, item_factory, user_factory, async_session
):
    admin = await user_factory()
    item = await item_factory(status=ItemStatus.PENDING_REVIEW)
    entry = await _create_queue_entry(async_session, item)

    service = ReviewQueueService(uow)
    updated_item = await service.reject(entry.id, admin.id, "Violates policy")

    await async_session.refresh(updated_item)
    assert updated_item.status == ItemStatus.REJECTED
    assert updated_item.rejection_reason == "Violates policy"
    assert updated_item.reviewed_by == admin.id


@pytest.mark.asyncio
async def test_reject_removes_queue_entry(
    uow, item_factory, user_factory, async_session
):
    admin = await user_factory()
    item = await item_factory(status=ItemStatus.PENDING_REVIEW)
    entry = await _create_queue_entry(async_session, item)
    entry_id = entry.id

    service = ReviewQueueService(uow)
    await service.reject(entry_id, admin.id, "Spam")
    refreshed = await async_session.get(ReviewQueue, entry_id)
    assert refreshed is None


@pytest.mark.asyncio
async def test_reject_raises_not_found_for_unknown_queue_id(uow, user_factory):
    admin = await user_factory()
    service = ReviewQueueService(uow)
    with pytest.raises(NotFoundError):
        await service.reject(uuid.uuid4(), admin.id, "reason")


# ---------------------------------------------------------------------------
# bulk_approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_approve_processes_all_provided_ids(
    uow, item_factory, user_factory, async_session
):
    admin = await user_factory()
    items = [await item_factory(status=ItemStatus.PENDING_REVIEW) for _ in range(3)]
    entries = [await _create_queue_entry(async_session, item) for item in items]

    service = ReviewQueueService(uow)
    result = await service.bulk_approve([e.id for e in entries], admin.id)

    assert result.successes == 3
    assert result.failures == []


@pytest.mark.asyncio
async def test_bulk_approve_partial_failure_reports_failed_ids(
    uow, item_factory, user_factory, async_session
):
    admin = await user_factory()
    item = await item_factory(status=ItemStatus.PENDING_REVIEW)
    entry = await _create_queue_entry(async_session, item)

    nonexistent = uuid.uuid4()

    service = ReviewQueueService(uow)
    result = await service.bulk_approve([entry.id, nonexistent], admin.id)

    assert result.successes == 1
    assert len(result.failures) == 1
    assert str(nonexistent) in result.failures[0].id


# ---------------------------------------------------------------------------
# bulk_reject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_reject_applies_same_reason_to_all(
    uow, item_factory, user_factory, async_session
):
    admin = await user_factory()
    items = [await item_factory(status=ItemStatus.PENDING_REVIEW) for _ in range(2)]
    entries = [await _create_queue_entry(async_session, item) for item in items]

    service = ReviewQueueService(uow)
    result = await service.bulk_reject([e.id for e in entries], admin.id, "Spam content")

    assert result.successes == 2
    assert result.failures == []

    for item in items:
        await async_session.refresh(item)
        assert item.rejection_reason == "Spam content"
        assert item.status == ItemStatus.REJECTED
