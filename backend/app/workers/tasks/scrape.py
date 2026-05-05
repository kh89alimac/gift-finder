"""Scrape task: run an adapter, dedup + upsert results, update job state."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.logging import get_logger
from app.core.redis import get_redis
from app.repositories.unit_of_work import UnitOfWork
from app.services.scraper_orchestrator import ScraperOrchestrator
from app.workers.celery_app import celery_app, run_async

log = get_logger("worker.scrape")


@celery_app.task(name="app.workers.tasks.scrape.scrape_site_task", bind=True)
def scrape_site_task(self: Any, site_id: int, job_id: str) -> dict[str, int]:
    """Execute a scrape job end-to-end.

    Streamed adapter results are batched into 50-item chunks before each
    DB commit so progress survives crashes. Progress lives in Redis under
    ``scrape:{job_id}:progress`` so the admin UI can poll without hammering
    the DB.
    """
    job_uuid = uuid.UUID(job_id)

    async def _run() -> dict[str, int]:
        totals = {"found": 0, "created": 0, "updated": 0, "skipped": 0}
        redis = get_redis()
        progress_key = f"scrape:{job_id}:progress"
        await redis.setex(progress_key, 24 * 3600, "0")

        async with UnitOfWork() as uow:
            orch = ScraperOrchestrator(uow)
            try:
                site = await orch.get_site(site_id)
            except Exception as exc:
                await orch.mark_job_failed(job_uuid, error=str(exc))
                await uow.commit()
                raise

            adapter_cls = orch.resolve_adapter(site.adapter_class)
            adapter = adapter_cls(site.config or {})

            buffer: list = []
            try:
                async for result in adapter.scrape():
                    buffer.append(result)
                    if len(buffer) >= 50:
                        stats = await orch.persist_scraped_batch(
                            buffer, job_id=job_uuid, site_id=site_id
                        )
                        for k, v in stats.items():
                            totals[k] = totals.get(k, 0) + v
                        await uow.commit()
                        await redis.setex(
                            progress_key, 24 * 3600, str(totals["found"])
                        )
                        buffer = []
                if buffer:
                    stats = await orch.persist_scraped_batch(
                        buffer, job_id=job_uuid, site_id=site_id
                    )
                    for k, v in stats.items():
                        totals[k] = totals.get(k, 0) + v
                    await uow.commit()

                await orch.mark_job_complete(
                    job_uuid,
                    items_found=totals["found"],
                    items_created=totals["created"],
                    items_updated=totals["updated"],
                    items_skipped=totals["skipped"],
                )
                await uow.commit()
            except Exception as exc:
                log.exception("scraper.task.failed", site_id=site_id, error=str(exc))
                await orch.mark_job_failed(
                    job_uuid, error=str(exc), will_retry=False
                )
                await uow.commit()
                raise

        await redis.delete(progress_key)
        return totals

    return run_async(_run())
