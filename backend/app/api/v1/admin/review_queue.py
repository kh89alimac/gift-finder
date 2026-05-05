"""Admin review-queue router."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Request, status

from app.api.rate_limit import limiter
from app.dependencies import AdminUser, UowDep
from app.models.enums import ItemSource
from app.schemas.common import BulkActionResult, PaginatedResponse
from app.schemas.items import ItemDetail
from app.schemas.review_queue import (
    ApproveRequest,
    BulkApproveRequest,
    BulkRejectRequest,
    RejectRequest,
    ReviewQueueFilters,
    ReviewQueueItem,
)
from app.services.review_queue_service import ReviewQueueService

router = APIRouter(prefix="/admin/review-queue", tags=["admin"])


@router.get("", response_model=PaginatedResponse[ReviewQueueItem])
async def list_queue(
    uow: UowDep,
    _admin: AdminUser,
    source: ItemSource | None = None,
    assigned_to: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> PaginatedResponse[ReviewQueueItem]:
    filters = ReviewQueueFilters(
        source=source,
        assigned_to=assigned_to,
        page=page,
        page_size=page_size,
    )
    service = ReviewQueueService(uow)
    return await service.list_queue(filters)


# Bulk routes MUST come before /{queue_id} routes so FastAPI doesn't try to
# coerce the literal string "bulk" as a UUID path parameter.
@router.post("/bulk/approve", response_model=BulkActionResult)
@limiter.limit("10/minute")
async def bulk_approve(
    request: Request,
    payload: BulkApproveRequest,
    uow: UowDep,
    admin: AdminUser,
) -> BulkActionResult:
    service = ReviewQueueService(uow)
    return await service.bulk_approve(payload.queue_ids, admin.id)


@router.post("/bulk/reject", response_model=BulkActionResult)
@limiter.limit("10/minute")
async def bulk_reject(
    request: Request,
    payload: BulkRejectRequest,
    uow: UowDep,
    admin: AdminUser,
) -> BulkActionResult:
    service = ReviewQueueService(uow)
    return await service.bulk_reject(payload.queue_ids, admin.id, payload.reason)


@router.get("/{queue_id}", response_model=ReviewQueueItem)
async def get_queue_item(
    queue_id: uuid.UUID,
    uow: UowDep,
    _admin: AdminUser,
) -> ReviewQueueItem:
    service = ReviewQueueService(uow)
    return await service.get_queue_item(queue_id)


@router.post("/{queue_id}/approve", response_model=ItemDetail)
async def approve(
    queue_id: uuid.UUID,
    payload: ApproveRequest,
    uow: UowDep,
    admin: AdminUser,
) -> ItemDetail:
    service = ReviewQueueService(uow)
    item = await service.approve(queue_id, admin.id, payload.item_patch)
    return ItemDetail.model_validate(item)


@router.post("/{queue_id}/reject", response_model=ItemDetail)
async def reject(
    queue_id: uuid.UUID,
    payload: RejectRequest,
    uow: UowDep,
    admin: AdminUser,
) -> ItemDetail:
    service = ReviewQueueService(uow)
    item = await service.reject(queue_id, admin.id, payload.reason)
    return ItemDetail.model_validate(item)
