"""Admin review-queue service.

Drives the moderation UI. ``ReviewQueue`` rows are created automatically
whenever an item lands in ``status=pending_review`` (we do that here in the
service rather than relying on a DB trigger). Approval flips the item to
ACTIVE; rejection sets ``status=REJECTED`` with a reason.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.admin import ReviewQueue
from app.models.catalog import Item
from app.models.enums import ItemStatus
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.common import BulkActionFailure, BulkActionResult, PageMeta, PaginatedResponse
from app.schemas.items import ItemSummary
from app.schemas.review_queue import (
    ItemApprovalPatch,
    ReviewQueueFilters,
    ReviewQueueItem,
)

log = get_logger(__name__)


class ReviewQueueService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ----------------------------------------------------------- list
    async def list_queue(
        self, filters: ReviewQueueFilters
    ) -> PaginatedResponse[ReviewQueueItem]:
        stmt = select(ReviewQueue).options(selectinload(ReviewQueue.item))
        count_stmt = select(func.count(ReviewQueue.id))

        if filters.source is not None:
            stmt = stmt.where(ReviewQueue.source == filters.source)
            count_stmt = count_stmt.where(ReviewQueue.source == filters.source)
        if filters.assigned_to is not None:
            stmt = stmt.where(ReviewQueue.assigned_to == filters.assigned_to)
            count_stmt = count_stmt.where(ReviewQueue.assigned_to == filters.assigned_to)

        stmt = (
            stmt.order_by(ReviewQueue.priority.asc(), ReviewQueue.created_at.asc())
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )

        result = await self.uow.session.execute(stmt)
        rows = list(result.scalars().all())

        total_result = await self.uow.session.execute(count_stmt)
        total = int(total_result.scalar_one())
        total_pages = (total + filters.page_size - 1) // filters.page_size

        items = [
            ReviewQueueItem(
                id=r.id,
                item_id=r.item_id,
                source=r.source,
                priority=r.priority,
                assigned_to=r.assigned_to,
                assigned_at=r.assigned_at,
                created_at=r.created_at,
                item=ItemSummary.model_validate(r.item) if r.item else None,
            )
            for r in rows
        ]
        return PaginatedResponse[ReviewQueueItem](
            items=items,
            meta=PageMeta(
                page=filters.page,
                page_size=filters.page_size,
                total=total,
                total_pages=total_pages,
            ),
        )

    async def get_queue_item(self, queue_id: uuid.UUID) -> ReviewQueueItem:
        stmt = (
            select(ReviewQueue)
            .where(ReviewQueue.id == queue_id)
            .options(selectinload(ReviewQueue.item))
        )
        result = await self.uow.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError(f"ReviewQueue {queue_id} not found")
        return ReviewQueueItem(
            id=row.id,
            item_id=row.item_id,
            source=row.source,
            priority=row.priority,
            assigned_to=row.assigned_to,
            assigned_at=row.assigned_at,
            created_at=row.created_at,
            item=ItemSummary.model_validate(row.item) if row.item else None,
        )

    # -------------------------------------------------------- approve
    async def approve(
        self,
        queue_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        item_patch: ItemApprovalPatch | None = None,
    ) -> Item:
        row = await self.uow.session.get(ReviewQueue, queue_id)
        if row is None:
            raise NotFoundError(f"ReviewQueue {queue_id} not found")
        item = await self.uow.items.get_by_id(row.item_id)
        if item is None:
            raise NotFoundError(f"Item {row.item_id} not found")

        # Apply the typed patch first, separately from the moderation columns
        # so an attacker can never use the patch to overwrite ``status`` etc.
        if item_patch is not None:
            update_data = item_patch.model_dump(exclude_none=True)
            if update_data:
                await self.uow.items.update(item, **update_data)

        await self.uow.items.update(
            item,
            status=ItemStatus.ACTIVE,
            reviewed_by=admin_user_id,
            reviewed_at=datetime.now(timezone.utc),
            published_at=item.published_at or datetime.now(timezone.utc),
        )
        # Remove from queue.
        await self.uow.session.delete(row)
        await self.uow.session.flush()
        return item

    # --------------------------------------------------------- reject
    async def reject(
        self,
        queue_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        reason: str,
    ) -> Item:
        row = await self.uow.session.get(ReviewQueue, queue_id)
        if row is None:
            raise NotFoundError(f"ReviewQueue {queue_id} not found")
        item = await self.uow.items.get_by_id(row.item_id)
        if item is None:
            raise NotFoundError(f"Item {row.item_id} not found")

        await self.uow.items.update(
            item,
            status=ItemStatus.REJECTED,
            rejection_reason=reason,
            reviewed_by=admin_user_id,
            reviewed_at=datetime.now(timezone.utc),
        )
        await self.uow.session.delete(row)
        await self.uow.session.flush()
        return item

    # ------------------------------------------------------ bulk ops
    async def bulk_approve(
        self,
        queue_ids: list[uuid.UUID],
        admin_user_id: uuid.UUID,
    ) -> BulkActionResult:
        """Approve every queue row in ``queue_ids`` with one UPDATE + DELETE.

        Anything we can't find is reported back as ``not_found`` rather than
        raising — admins want partial success on bulk actions.
        """
        now = datetime.now(timezone.utc)
        result = await self.uow.session.execute(
            select(ReviewQueue.id, ReviewQueue.item_id).where(
                ReviewQueue.id.in_(queue_ids)
            )
        )
        rows = result.all()
        item_ids = [r.item_id for r in rows]
        found_ids = [r.id for r in rows]
        missing_ids = [qid for qid in queue_ids if qid not in set(found_ids)]

        if item_ids:
            try:
                await self.uow.session.execute(
                    sa_update(Item)
                    .where(Item.id.in_(item_ids))
                    .values(
                        status=ItemStatus.ACTIVE,
                        reviewed_by=admin_user_id,
                        reviewed_at=now,
                    )
                )
                await self.uow.session.execute(
                    sa_delete(ReviewQueue).where(ReviewQueue.id.in_(found_ids))
                )
                await self.uow.session.flush()
            except Exception:
                # Don't surface DB internals to the client — log full
                # exception server-side so we can still triage.
                log.exception("review_queue.bulk_approve.failed")
                return BulkActionResult(
                    successes=0,
                    failures=[
                        BulkActionFailure(id=str(qid), reason="approval_failed")
                        for qid in queue_ids
                    ],
                )

        return BulkActionResult(
            successes=len(found_ids),
            failures=[
                BulkActionFailure(id=str(qid), reason="not_found")
                for qid in missing_ids
            ],
        )

    async def bulk_reject(
        self,
        queue_ids: list[uuid.UUID],
        admin_user_id: uuid.UUID,
        reason: str,
    ) -> BulkActionResult:
        """Reject every queue row in ``queue_ids`` with one UPDATE + DELETE."""
        now = datetime.now(timezone.utc)
        result = await self.uow.session.execute(
            select(ReviewQueue.id, ReviewQueue.item_id).where(
                ReviewQueue.id.in_(queue_ids)
            )
        )
        rows = result.all()
        item_ids = [r.item_id for r in rows]
        found_ids = [r.id for r in rows]
        missing_ids = [qid for qid in queue_ids if qid not in set(found_ids)]

        if item_ids:
            try:
                await self.uow.session.execute(
                    sa_update(Item)
                    .where(Item.id.in_(item_ids))
                    .values(
                        status=ItemStatus.REJECTED,
                        rejection_reason=reason,
                        reviewed_by=admin_user_id,
                        reviewed_at=now,
                    )
                )
                await self.uow.session.execute(
                    sa_delete(ReviewQueue).where(ReviewQueue.id.in_(found_ids))
                )
                await self.uow.session.flush()
            except Exception:
                log.exception("review_queue.bulk_reject.failed")
                return BulkActionResult(
                    successes=0,
                    failures=[
                        BulkActionFailure(id=str(qid), reason="rejection_failed")
                        for qid in queue_ids
                    ],
                )

        return BulkActionResult(
            successes=len(found_ids),
            failures=[
                BulkActionFailure(id=str(qid), reason="not_found")
                for qid in missing_ids
            ],
        )
