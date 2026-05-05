"""Embed task: compute and persist a vector for a single item."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.logging import get_logger
from app.integrations.openai_client import embed_one
from app.repositories.unit_of_work import UnitOfWork
from app.workers.celery_app import celery_app, run_async

log = get_logger("worker.embed")


def _embedding_text(item: Any) -> str:
    """Compose the text we'll embed.

    Title weighted by repetition is a cheap-but-effective trick: terms in
    the title carry more weight in the resulting vector. Description is
    truncated to keep token usage predictable.
    """
    title = item.title or ""
    description = (item.description or "")[:1500]
    brand = item.brand or ""
    retailer = item.retailer or ""
    return f"{title}\n{title}\n{description}\nBrand: {brand}\nRetailer: {retailer}".strip()


@celery_app.task(
    name="app.workers.tasks.embed.embed_item_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def embed_item_task(self: Any, item_id: str) -> bool:
    item_uuid = uuid.UUID(item_id)

    async def _run() -> bool:
        async with UnitOfWork() as uow:
            item = await uow.items.get_by_id(item_uuid)
            if item is None:
                log.warning("embed.item_not_found", item_id=item_id)
                return False

            embedding = await embed_one(_embedding_text(item))
            await uow.items.update(item, embedding=embedding)
            await uow.commit()
            return True

    return run_async(_run())
