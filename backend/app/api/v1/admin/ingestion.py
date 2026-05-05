"""Admin ingestion endpoints: scrapers, instagram queue, manual entry, CSV/image upload."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Query, Request, UploadFile, status

from app.api.rate_limit import limiter
from app.core.exceptions import ValidationError
from app.dependencies import AdminUser, UowDep
from app.schemas.ingestion import (
    CsvImportResult,
    ImageUploadResponse,
    InstagramQueueItem,
    InstagramTriggerRequest,
    ScraperJobOut,
    ScraperTriggerRequest,
)
from app.schemas.items import ItemDetail, ItemManualIn, ItemManualUpdate
from app.services.instagram_ingestion_service import InstagramIngestionService
from app.services.manual_ingestion_service import ManualIngestionService
from app.services.scraper_orchestrator import ScraperOrchestrator

router = APIRouter(prefix="/admin/ingestion", tags=["admin"])


# ---------------------------------------------------------------- scraper


@router.post(
    "/scraper/trigger",
    response_model=ScraperJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("30/minute")
async def trigger_scraper(
    request: Request,
    payload: ScraperTriggerRequest,
    uow: UowDep,
    _admin: AdminUser,
) -> ScraperJobOut:
    service = ScraperOrchestrator(uow)
    job = await service.trigger_site(payload.site_id, priority=payload.priority)

    # Best-effort dispatch to Celery; falls through if broker is unavailable
    # so the job stays QUEUED for the next worker to claim.
    try:
        from app.workers.tasks.scrape import scrape_site_task

        scrape_site_task.apply_async(  # type: ignore[attr-defined]
            kwargs={"site_id": payload.site_id, "job_id": str(job.id)}
        )
    except Exception:
        pass

    return ScraperJobOut.model_validate(job)


@router.get("/scraper/jobs", response_model=list[ScraperJobOut])
async def list_scraper_jobs(
    uow: UowDep,
    _admin: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ScraperJobOut]:
    jobs = await uow.scraper_jobs.list(
        limit=limit, order_by=None, offset=0
    )
    # ``list`` doesn't accept order_by None gracefully — use raw SQL for clarity.
    from sqlalchemy import select

    from app.models.ingestion import ScraperJob

    result = await uow.session.execute(
        select(ScraperJob).order_by(ScraperJob.created_at.desc()).limit(limit)
    )
    jobs = list(result.scalars().all())
    return [ScraperJobOut.model_validate(j) for j in jobs]


# -------------------------------------------------------------- instagram


@router.post(
    "/instagram/trigger",
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/minute")
async def trigger_instagram(
    request: Request,
    payload: InstagramTriggerRequest,
    uow: UowDep,
    _admin: AdminUser,
) -> dict[str, str]:
    """Enqueue an instagram fetch task. Returns the celery task id."""
    try:
        from app.workers.tasks.instagram import instagram_fetch_task

        async_result = instagram_fetch_task.apply_async(  # type: ignore[attr-defined]
            kwargs={
                "target": payload.target,
                "target_type": payload.target_type,
                "limit": payload.limit,
            }
        )
        return {"task_id": str(async_result.id)}
    except Exception as exc:
        raise ValidationError(f"Failed to dispatch Instagram task: {exc}") from exc


@router.get("/instagram/queue", response_model=list[InstagramQueueItem])
async def list_instagram_queue(
    uow: UowDep,
    _admin: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[InstagramQueueItem]:
    service = InstagramIngestionService(uow)
    return await service.list_pending(limit=limit)


@router.post(
    "/instagram/queue/{queue_id}/approve",
    response_model=InstagramQueueItem,
)
async def approve_instagram_queue(
    queue_id: uuid.UUID,
    uow: UowDep,
    admin: AdminUser,
) -> InstagramQueueItem:
    service = InstagramIngestionService(uow)
    return await service.approve_queue_item(queue_id, admin.id)


@router.post(
    "/instagram/queue/{queue_id}/reject",
    response_model=InstagramQueueItem,
)
async def reject_instagram_queue(
    queue_id: uuid.UUID,
    uow: UowDep,
    admin: AdminUser,
    reason: str | None = None,
) -> InstagramQueueItem:
    service = InstagramIngestionService(uow)
    return await service.reject_queue_item(queue_id, admin.id, reason)


# -------------------------------------------------------------- manual


@router.post(
    "/manual/items",
    response_model=ItemDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_item(
    payload: ItemManualIn,
    uow: UowDep,
    admin: AdminUser,
) -> ItemDetail:
    service = ManualIngestionService(uow)
    item = await service.create_item(payload, admin.id)
    return ItemDetail.model_validate(item)


@router.patch("/manual/items/{item_id}", response_model=ItemDetail)
async def update_manual_item(
    item_id: uuid.UUID,
    payload: ItemManualUpdate,
    uow: UowDep,
    admin: AdminUser,
) -> ItemDetail:
    service = ManualIngestionService(uow)
    item = await service.update_item(item_id, payload, admin.id)
    return ItemDetail.model_validate(item)


@router.post(
    "/manual/items/{item_id}/image",
    response_model=ImageUploadResponse,
)
async def upload_item_image(
    item_id: uuid.UUID,
    uow: UowDep,
    admin: AdminUser,
    file: UploadFile = File(...),
) -> ImageUploadResponse:
    raw = await file.read()
    if not raw:
        raise ValidationError("Empty upload")
    service = ManualIngestionService(uow)
    return await service.upload_image(
        item_id, raw, admin.id, filename=file.filename
    )


@router.post(
    "/manual/csv-import",
    response_model=CsvImportResult,
)
async def import_csv(
    uow: UowDep,
    admin: AdminUser,
    file: UploadFile = File(...),
) -> CsvImportResult:
    raw = await file.read()
    if not raw:
        raise ValidationError("Empty CSV upload")
    service = ManualIngestionService(uow)
    return await service.import_csv(raw, admin.id)
