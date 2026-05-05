"""Scraper job queue repository.

Workers claim jobs with ``SELECT ... FOR UPDATE SKIP LOCKED`` so multiple
workers can poll the table concurrently without blocking each other or
double-claiming the same job. The lock is held until the worker's transaction
commits, which is when the status flips to ``RUNNING``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import JobStatus
from app.models.ingestion import ScraperJob
from app.repositories.base import BaseRepository


class ScraperJobRepository(BaseRepository[ScraperJob]):
    model = ScraperJob

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ScraperJob)

    async def claim_next_job(
        self, *, site_id: int | None = None
    ) -> ScraperJob | None:
        """Atomically claim the next queued job and mark it RUNNING.

        Pass ``site_id`` to limit the claim to one site (e.g. site-specific
        worker pools). Returns ``None`` if the queue is empty.

        The select-and-update pair must run inside the caller's transaction;
        commit responsibility stays with the unit of work.
        """
        select_stmt = (
            select(ScraperJob.id)
            .where(
                ScraperJob.status == JobStatus.QUEUED,
                ScraperJob.retry_count <= ScraperJob.max_retries,
            )
            .order_by(ScraperJob.priority.asc(), ScraperJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if site_id is not None:
            select_stmt = select_stmt.where(ScraperJob.site_id == site_id)

        result = await self.session.execute(select_stmt)
        job_id = result.scalar_one_or_none()
        if job_id is None:
            return None

        # Flip status to RUNNING and stamp started_at.
        await self.session.execute(
            update(ScraperJob)
            .where(ScraperJob.id == job_id)
            .values(
                status=JobStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                updated_at=func.now(),
            )
        )
        # Expire any stale identity-map entry so get() re-fetches from DB.
        await self.session.flush()
        job = await self.get_by_id_or_raise(job_id)
        await self.session.refresh(job)
        return job

    async def mark_completed(
        self,
        job_id: uuid.UUID,
        *,
        items_found: int,
        items_created: int,
        items_updated: int,
        items_skipped: int,
    ) -> None:
        """Record successful completion stats."""
        await self.session.execute(
            update(ScraperJob)
            .where(ScraperJob.id == job_id)
            .values(
                status=JobStatus.COMPLETED,
                completed_at=datetime.now(timezone.utc),
                items_found=items_found,
                items_created=items_created,
                items_updated=items_updated,
                items_skipped=items_skipped,
                error_message=None,
                updated_at=func.now(),
            )
        )

    async def mark_failed(
        self,
        job_id: uuid.UUID,
        *,
        error_message: str,
        will_retry: bool,
    ) -> None:
        """Record failure. If ``will_retry`` the status returns to QUEUED."""
        new_status = JobStatus.QUEUED if will_retry else JobStatus.FAILED
        await self.session.execute(
            update(ScraperJob)
            .where(ScraperJob.id == job_id)
            .values(
                status=new_status,
                completed_at=datetime.now(timezone.utc) if not will_retry else None,
                error_message=error_message,
                retry_count=ScraperJob.retry_count + 1,
                updated_at=func.now(),
            )
        )

    async def list_running(self) -> list[ScraperJob]:
        """All currently-running jobs (useful for ops dashboards)."""
        stmt = (
            select(ScraperJob)
            .where(ScraperJob.status == JobStatus.RUNNING)
            .order_by(ScraperJob.started_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
