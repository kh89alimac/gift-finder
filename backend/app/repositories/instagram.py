"""Instagram review queue repository.

Admins claim batches of pending posts to review. We use SKIP LOCKED so two
admins reviewing simultaneously never see the same row.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InstagramQueueStatus
from app.models.ingestion import InstagramQueue
from app.repositories.base import BaseRepository


class InstagramQueueRepository(BaseRepository[InstagramQueue]):
    model = InstagramQueue

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, InstagramQueue)

    async def claim_pending(
        self, admin_user_id: uuid.UUID, *, limit: int = 10
    ) -> list[InstagramQueue]:
        """Claim up to ``limit`` pending posts for the given admin to review.

        We optimistically assign ``reviewed_by`` to soft-lock the rows for the
        admin's session — the actual status flip happens when they
        approve/reject. SKIP LOCKED prevents two admins racing for the same
        batch.
        """
        select_stmt = (
            select(InstagramQueue.id)
            .where(InstagramQueue.status == InstagramQueueStatus.PENDING)
            .order_by(
                InstagramQueue.confidence_score.desc(),
                InstagramQueue.created_at.asc(),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(select_stmt)
        ids = [row for row in result.scalars().all()]
        if not ids:
            return []

        await self.session.execute(
            update(InstagramQueue)
            .where(InstagramQueue.id.in_(ids))
            .values(reviewed_by=admin_user_id, updated_at=func.now())
        )

        fetch_stmt = select(InstagramQueue).where(InstagramQueue.id.in_(ids))
        result2 = await self.session.execute(fetch_stmt)
        return list(result2.scalars().all())

    async def approve(
        self,
        queue_id: uuid.UUID,
        *,
        admin_user_id: uuid.UUID,
        promoted_item_id: uuid.UUID,
    ) -> None:
        """Mark a queue entry approved and link to the created item."""
        await self.session.execute(
            update(InstagramQueue)
            .where(InstagramQueue.id == queue_id)
            .values(
                status=InstagramQueueStatus.APPROVED,
                reviewed_by=admin_user_id,
                reviewed_at=datetime.now(timezone.utc),
                promoted_item_id=promoted_item_id,
                updated_at=func.now(),
            )
        )

    async def reject(self, queue_id: uuid.UUID, *, admin_user_id: uuid.UUID) -> None:
        """Mark a queue entry rejected."""
        await self.session.execute(
            update(InstagramQueue)
            .where(InstagramQueue.id == queue_id)
            .values(
                status=InstagramQueueStatus.REJECTED,
                reviewed_by=admin_user_id,
                reviewed_at=datetime.now(timezone.utc),
                updated_at=func.now(),
            )
        )

    async def get_by_instagram_id(self, instagram_post_id: str) -> InstagramQueue | None:
        """Look up an entry by its native Instagram post id (for dedup on ingest)."""
        stmt = select(InstagramQueue).where(
            InstagramQueue.instagram_post_id == instagram_post_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
