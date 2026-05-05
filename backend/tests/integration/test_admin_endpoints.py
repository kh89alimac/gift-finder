"""Integration tests for admin endpoints (/api/v1/admin/*)."""

from __future__ import annotations

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.admin import ReviewQueue
from app.models.enums import ItemSource, ItemStatus, UserRole


QUEUE_BASE = "/api/v1/admin/review-queue"
TAXONOMY_BASE = "/api/v1/admin/taxonomy"
INGESTION_BASE = "/api/v1/admin/ingestion"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_queue_entry(async_session, item, source=ItemSource.MANUAL):
    entry = ReviewQueue(item_id=item.id, source=source, priority=5)
    async_session.add(entry)
    await async_session.flush()
    return entry


# ---------------------------------------------------------------------------
# Auth guards: 401 without token, 403 with non-admin token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_queue_returns_401_without_token(test_client):
    resp = await test_client.get(QUEUE_BASE)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_queue_returns_403_with_non_admin_token(
    test_client, user_factory, auth_headers
):
    user = await user_factory()  # role=USER
    resp = await test_client.get(QUEUE_BASE, headers=auth_headers(user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_taxonomy_returns_401_without_token(test_client):
    resp = await test_client.get(f"{TAXONOMY_BASE}/tag-types")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_taxonomy_returns_403_for_non_admin(
    test_client, user_factory, auth_headers
):
    user = await user_factory()
    resp = await test_client.get(
        f"{TAXONOMY_BASE}/tag-types", headers=auth_headers(user)
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/review-queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_review_queue_returns_items(
    test_client, admin_factory, item_factory, auth_headers, async_session
):
    admin = await admin_factory()
    item = await item_factory(status=ItemStatus.PENDING_REVIEW)
    await _create_queue_entry(async_session, item)

    resp = await test_client.get(
        QUEUE_BASE, headers=auth_headers(admin)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert body["meta"]["total"] >= 1


# ---------------------------------------------------------------------------
# POST /admin/review-queue/{id}/approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_changes_item_status_to_active(
    test_client, admin_factory, item_factory, auth_headers, async_session
):
    admin = await admin_factory()
    item = await item_factory(status=ItemStatus.PENDING_REVIEW)
    entry = await _create_queue_entry(async_session, item)

    resp = await test_client.post(
        f"{QUEUE_BASE}/{entry.id}/approve",
        json={"item_patch": {}},
        headers=auth_headers(admin),
    )
    assert resp.status_code == 200
    await async_session.refresh(item)
    assert item.status == ItemStatus.ACTIVE


# ---------------------------------------------------------------------------
# POST /admin/review-queue/{id}/reject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_changes_item_status_to_rejected(
    test_client, admin_factory, item_factory, auth_headers, async_session
):
    admin = await admin_factory()
    item = await item_factory(status=ItemStatus.PENDING_REVIEW)
    entry = await _create_queue_entry(async_session, item)

    resp = await test_client.post(
        f"{QUEUE_BASE}/{entry.id}/reject",
        json={"reason": "Spam"},
        headers=auth_headers(admin),
    )
    assert resp.status_code == 200
    await async_session.refresh(item)
    assert item.status == ItemStatus.REJECTED


# ---------------------------------------------------------------------------
# POST /admin/review-queue/bulk/approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_approve_approves_multiple_items(
    test_client, admin_factory, item_factory, auth_headers, async_session
):
    admin = await admin_factory()
    items = [await item_factory(status=ItemStatus.PENDING_REVIEW) for _ in range(2)]
    entries = [await _create_queue_entry(async_session, item) for item in items]

    resp = await test_client.post(
        f"{QUEUE_BASE}/bulk/approve",
        json={"queue_ids": [str(e.id) for e in entries]},
        headers=auth_headers(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["successes"] == 2
    assert body["failures"] == []


# ---------------------------------------------------------------------------
# GET /admin/taxonomy/tag-types
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tag_types_returns_list(
    test_client, admin_factory, auth_headers, tag_type_factory
):
    admin = await admin_factory()
    await tag_type_factory(name="test-type-unique")

    resp = await test_client.get(
        f"{TAXONOMY_BASE}/tag-types", headers=auth_headers(admin)
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    names = [t["name"] for t in resp.json()]
    assert "test-type-unique" in names


# ---------------------------------------------------------------------------
# POST /admin/ingestion/scraper/trigger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_scraper_returns_202_with_job_id(
    test_client, admin_factory, scraper_site_factory, auth_headers, mocker
):
    admin = await admin_factory()
    site = await scraper_site_factory(is_active=True)

    # Prevent actual Celery dispatch by patching the celery task module.
    # The route handler imports the task lazily inside a try/except, so we
    # patch the module attribute it would import from.
    fake_task = MagicMock()
    fake_task.apply_async = MagicMock(return_value=None)
    mocker.patch.dict(
        "sys.modules",
        {"app.workers.tasks.scrape": MagicMock(scrape_site_task=fake_task)},
    )

    resp = await test_client.post(
        f"{INGESTION_BASE}/scraper/trigger",
        json={"site_id": site.id, "priority": 5},
        headers=auth_headers(admin),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "id" in body  # job_id returned in ScraperJobOut


# ---------------------------------------------------------------------------
# POST /admin/ingestion/manual/csv-import
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_csv_import_valid_csv_returns_accepted_count(
    test_client, admin_factory, auth_headers
):
    admin = await admin_factory()
    csv_content = b"title,price,currency\nGift Box,19.99,USD\nBook Set,12.00,USD\n"

    resp = await test_client.post(
        f"{INGESTION_BASE}/manual/csv-import",
        headers=auth_headers(admin),
        files={"file": ("import.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 2
    assert body["skipped"] == 0


@pytest.mark.asyncio
async def test_csv_import_empty_file_returns_error(
    test_client, admin_factory, auth_headers
):
    admin = await admin_factory()
    resp = await test_client.post(
        f"{INGESTION_BASE}/manual/csv-import",
        headers=auth_headers(admin),
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert resp.status_code in {400, 422}


@pytest.mark.asyncio
async def test_csv_import_without_admin_token_returns_401(test_client):
    csv_content = b"title,price\nItem,9.99\n"
    resp = await test_client.post(
        f"{INGESTION_BASE}/manual/csv-import",
        files={"file": ("import.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 401
