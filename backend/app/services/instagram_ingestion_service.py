"""Instagram ingestion service.

Two flows:

* **fetch_and_queue** — pull recent media for a user/hashtag and enqueue
  candidate posts. Runs in a worker; idempotent on (instagram_post_id).
* **approve / reject** — admins promote a queued post to a real ``Item``
  (approve) or discard it (reject).

We don't re-host Instagram images on S3 here — that's the manual ingestion
service's job once the post is approved. Storing the IG CDN URL is fine for
the queue.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.core.exceptions import ConflictError, ExternalServiceError, NotFoundError
from app.core.logging import get_logger
from app.core.safe_http import validate_display_url
from app.integrations.instagram_client import get_hashtag_media, get_user_media
from app.models.enums import InstagramQueueStatus, ItemSource, ItemStatus
from app.models.ingestion import InstagramQueue
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.ingestion import InstagramQueueItem

log = get_logger(__name__)


class InstagramIngestionService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ----------------------------------------------------- fetch+queue
    async def fetch_and_queue(
        self,
        target: str,
        target_type: str,
        *,
        access_token: str | None = None,
        limit: int = 25,
    ) -> int:
        """Fetch recent posts and insert pending queue rows.

        Returns the count of *newly* queued posts (existing IG ids are
        idempotently ignored so re-runs don't duplicate).
        """
        token = access_token or os.environ.get("INSTAGRAM_ACCESS_TOKEN")
        if not token:
            raise ExternalServiceError("Instagram access token is not configured")

        if target_type == "user":
            posts = await get_user_media(target, token, limit=limit)
        elif target_type == "hashtag":
            posts = await get_hashtag_media(target, token, limit=limit)
        else:
            raise ValueError(f"Unsupported target_type: {target_type}")

        new_count = 0
        for post in posts:
            ig_id = str(post.get("id") or "")
            if not ig_id:
                continue

            existing = await self.uow.instagram.get_by_instagram_id(ig_id)
            if existing is not None:
                continue

            caption = post.get("caption") or ""
            hashtags = _extract_hashtags(caption)
            # Reject any non-http(s) URLs surfaced by the Instagram payload
            # before storing — protects downstream renderers from javascript:
            # / data: smuggling.
            raw_media = post.get("media_url") or post.get("thumbnail_url") or ""
            safe_media = validate_display_url(str(raw_media)) or ""
            safe_permalink = validate_display_url(str(post.get("permalink") or "")) or ""
            queue_row = InstagramQueue(
                instagram_post_id=ig_id,
                permalink=safe_permalink,
                image_url=safe_media,
                caption=caption or None,
                account_handle=str(post.get("username") or "unknown"),
                hashtags=hashtags,
                suggested_tags={},
                confidence_score=Decimal("0"),
                status=InstagramQueueStatus.PENDING,
                raw_data=dict(post),
            )
            self.uow.session.add(queue_row)
            new_count += 1

        await self.uow.session.flush()
        return new_count

    # -------------------------------------------------------- approve
    async def approve_queue_item(
        self,
        queue_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        item_patch: dict[str, Any] | None = None,
    ) -> InstagramQueueItem:
        queue_row = await self.uow.instagram.get_by_id(queue_id)
        if queue_row is None:
            raise NotFoundError(f"InstagramQueue {queue_id} not found")
        if queue_row.status != InstagramQueueStatus.PENDING:
            raise ConflictError(f"Queue item is already {queue_row.status}")

        # Promote to a real Item.
        patch = item_patch or {}
        from app.models.catalog import Item  # local import to avoid circular

        item = Item(
            title=(patch.get("title") or _title_from_caption(queue_row.caption)),
            description=patch.get("description") or queue_row.caption,
            image_url=patch.get("image_url") or queue_row.image_url,
            product_url=patch.get("product_url"),
            source=ItemSource.INSTAGRAM,
            source_external_id=queue_row.instagram_post_id,
            source_url=queue_row.permalink,
            status=ItemStatus.ACTIVE,
            reviewed_by=admin_user_id,
            reviewed_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc),
        )
        self.uow.session.add(item)
        await self.uow.session.flush()

        # Apply caller-supplied tags if any.
        tag_ids = patch.get("tag_ids", [])
        if tag_ids:
            from app.models.catalog import ItemTag

            for tid in tag_ids:
                self.uow.session.add(ItemTag(item_id=item.id, tag_id=int(tid)))

        await self.uow.instagram.approve(
            queue_id,
            admin_user_id=admin_user_id,
            promoted_item_id=item.id,
        )

        # Re-fetch row with new state for response.
        await self.uow.session.refresh(queue_row)
        return InstagramQueueItem.model_validate(queue_row)

    # -------------------------------------------------------- reject
    async def reject_queue_item(
        self,
        queue_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        reason: str | None = None,
    ) -> InstagramQueueItem:
        queue_row = await self.uow.instagram.get_by_id(queue_id)
        if queue_row is None:
            raise NotFoundError(f"InstagramQueue {queue_id} not found")
        if queue_row.status != InstagramQueueStatus.PENDING:
            raise ConflictError(f"Queue item is already {queue_row.status}")

        await self.uow.instagram.reject(queue_id, admin_user_id=admin_user_id)
        await self.uow.session.refresh(queue_row)
        if reason:
            # Record reason in raw_data so we don't lose context; we don't have a
            # dedicated column.
            updated = dict(queue_row.raw_data)
            updated["rejection_reason"] = reason
            queue_row.raw_data = updated
            await self.uow.session.flush()
        return InstagramQueueItem.model_validate(queue_row)

    # ---------------------------------------------------------- list
    async def list_pending(
        self, *, limit: int = 50
    ) -> list[InstagramQueueItem]:
        from sqlalchemy import select

        stmt = (
            select(InstagramQueue)
            .where(InstagramQueue.status == InstagramQueueStatus.PENDING)
            .order_by(InstagramQueue.created_at.desc())
            .limit(limit)
        )
        result = await self.uow.session.execute(stmt)
        rows = list(result.scalars().all())
        return [InstagramQueueItem.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_hashtags(caption: str) -> list[str]:
    """Pull ``#hashtag`` tokens from an IG caption."""
    if not caption:
        return []
    out = []
    for token in caption.split():
        if token.startswith("#") and len(token) > 1:
            cleaned = token.strip("#.,!?;:'\"()[]").lower()
            if cleaned:
                out.append(cleaned)
    return out


def _title_from_caption(caption: str | None) -> str:
    if not caption:
        return "Instagram product"
    # First line, truncated to 200 chars (well under our 500 column limit).
    first_line = caption.splitlines()[0].strip()
    return first_line[:200] or "Instagram product"
