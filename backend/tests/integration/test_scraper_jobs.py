"""Integration tests for ScraperJobRepository: claim_next_job, mark_completed/failed.

These tests exercise the repository directly via the ``uow`` fixture against
the in-memory SQLite database. SKIP LOCKED behavior is structural to
PostgreSQL; the SQLite shim tests the surrounding logic (status transitions,
retry_count, etc.) that is portable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.enums import JobStatus
from app.models.ingestion import ScraperJob


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_job(
    session,
    site_id: int | None = None,
    status: JobStatus = JobStatus.QUEUED,
    priority: int = 5,
) -> ScraperJob:
    job = ScraperJob(site_id=site_id, status=status, priority=priority)
    session.add(job)
    await session.flush()
    return job


# ---------------------------------------------------------------------------
# claim_next_job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_next_job_claims_queued_job_and_marks_it_running(
    uow, scraper_site_factory, async_session
):
    site = await scraper_site_factory()
    job = await _create_job(async_session, site_id=site.id)
    assert job.status == JobStatus.QUEUED

    claimed = await uow.scraper_jobs.claim_next_job(site_id=site.id)

    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == JobStatus.RUNNING
    assert claimed.started_at is not None


@pytest.mark.asyncio
async def test_claim_next_job_returns_none_when_queue_empty(uow):
    result = await uow.scraper_jobs.claim_next_job()
    assert result is None


@pytest.mark.asyncio
async def test_claim_next_job_respects_priority_order(
    uow, scraper_site_factory, async_session
):
    """Lower priority number = higher urgency — should be claimed first."""
    site = await scraper_site_factory()
    low_priority = await _create_job(async_session, site_id=site.id, priority=10)
    high_priority = await _create_job(async_session, site_id=site.id, priority=1)

    claimed = await uow.scraper_jobs.claim_next_job(site_id=site.id)
    assert claimed is not None
    assert claimed.id == high_priority.id


@pytest.mark.asyncio
async def test_claim_next_job_skip_locked_does_not_claim_running_job(
    uow, scraper_site_factory, async_session
):
    """A job already in RUNNING status must not be re-claimed."""
    site = await scraper_site_factory()
    await _create_job(async_session, site_id=site.id, status=JobStatus.RUNNING)

    # Only a RUNNING job is in the table — nothing to claim.
    claimed = await uow.scraper_jobs.claim_next_job(site_id=site.id)
    assert claimed is None


@pytest.mark.asyncio
async def test_claim_next_job_skips_failed_job(
    uow, scraper_site_factory, async_session
):
    site = await scraper_site_factory()
    await _create_job(async_session, site_id=site.id, status=JobStatus.FAILED)
    claimed = await uow.scraper_jobs.claim_next_job(site_id=site.id)
    assert claimed is None


# ---------------------------------------------------------------------------
# mark_completed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_job_complete_updates_status_and_stats(
    uow, scraper_site_factory, async_session
):
    site = await scraper_site_factory()
    job = await _create_job(async_session, site_id=site.id, status=JobStatus.RUNNING)

    await uow.scraper_jobs.mark_completed(
        job.id,
        items_found=100,
        items_created=80,
        items_updated=15,
        items_skipped=5,
    )
    await async_session.flush()
    await async_session.refresh(job)

    assert job.status == JobStatus.COMPLETED
    assert job.items_found == 100
    assert job.items_created == 80
    assert job.items_updated == 15
    assert job.items_skipped == 5
    assert job.completed_at is not None
    assert job.error_message is None


# ---------------------------------------------------------------------------
# mark_failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_job_failed_increments_retry_count(
    uow, scraper_site_factory, async_session
):
    site = await scraper_site_factory()
    job = await _create_job(async_session, site_id=site.id, status=JobStatus.RUNNING)
    assert job.retry_count == 0

    await uow.scraper_jobs.mark_failed(
        job.id, error_message="Connection refused", will_retry=True
    )
    await async_session.flush()
    await async_session.refresh(job)

    assert job.retry_count == 1
    assert job.error_message == "Connection refused"
    # will_retry=True: status goes back to QUEUED.
    assert job.status == JobStatus.QUEUED


@pytest.mark.asyncio
async def test_mark_job_failed_without_retry_sets_failed_status(
    uow, scraper_site_factory, async_session
):
    site = await scraper_site_factory()
    job = await _create_job(async_session, site_id=site.id, status=JobStatus.RUNNING)

    await uow.scraper_jobs.mark_failed(
        job.id, error_message="Max retries exceeded", will_retry=False
    )
    await async_session.flush()
    await async_session.refresh(job)

    assert job.status == JobStatus.FAILED
    assert job.retry_count == 1


@pytest.mark.asyncio
async def test_mark_job_failed_three_times_reflects_retry_count(
    uow, scraper_site_factory, async_session
):
    """Calling mark_failed multiple times keeps incrementing retry_count."""
    site = await scraper_site_factory()
    job = await _create_job(async_session, site_id=site.id, status=JobStatus.RUNNING)

    for _ in range(3):
        await uow.scraper_jobs.mark_failed(
            job.id, error_message="err", will_retry=True
        )
        await async_session.flush()

    await async_session.refresh(job)
    assert job.retry_count == 3
