"""Instagram fetch task with simple Redis-based rate limiting."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.core.redis import get_redis
from app.repositories.unit_of_work import UnitOfWork
from app.services.instagram_ingestion_service import InstagramIngestionService
from app.workers.celery_app import celery_app, run_async

log = get_logger("worker.instagram")

# Instagram Graph API allows ~200 calls/hour/user; we cap at 60/hour to be safe.
RATE_KEY = "instagram:fetch_count_hourly"
RATE_LIMIT = 60
RATE_TTL_SECONDS = 3600


@celery_app.task(
    name="app.workers.tasks.instagram.instagram_fetch_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def instagram_fetch_task(
    self: Any,
    target: str,
    target_type: str,
    limit: int = 25,
) -> int:
    async def _run() -> int:
        redis = get_redis()
        # INCR + EXPIRE pattern; EXPIRE only sets TTL on first hit of the window.
        count = await redis.incr(RATE_KEY)
        if count == 1:
            await redis.expire(RATE_KEY, RATE_TTL_SECONDS)
        if count > RATE_LIMIT:
            log.warning("instagram.rate_limit.exceeded", count=count)
            raise RuntimeError("Instagram rate limit exceeded; backing off")

        async with UnitOfWork() as uow:
            service = InstagramIngestionService(uow)
            queued = await service.fetch_and_queue(
                target=target,
                target_type=target_type,
                limit=limit,
            )
            await uow.commit()
            return queued

    return run_async(_run())
