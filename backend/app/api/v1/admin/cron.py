"""Admin cron-schedule CRUD + manual trigger."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.dependencies import AdminUser, UowDep
from app.schemas.cron import CronScheduleIn, CronScheduleOut, CronScheduleUpdate
from app.services.cron_scheduler_service import CronSchedulerService

router = APIRouter(prefix="/admin/cron", tags=["admin"])


@router.get("", response_model=list[CronScheduleOut])
async def list_schedules(uow: UowDep, _admin: AdminUser) -> list[CronScheduleOut]:
    service = CronSchedulerService(uow)
    return await service.list_schedules()


@router.post("", response_model=CronScheduleOut, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: CronScheduleIn, uow: UowDep, _admin: AdminUser
) -> CronScheduleOut:
    service = CronSchedulerService(uow)
    return await service.create_schedule(payload)


@router.get("/{schedule_id}", response_model=CronScheduleOut)
async def get_schedule(
    schedule_id: int, uow: UowDep, _admin: AdminUser
) -> CronScheduleOut:
    service = CronSchedulerService(uow)
    return await service.get(schedule_id)


@router.patch("/{schedule_id}", response_model=CronScheduleOut)
async def update_schedule(
    schedule_id: int,
    payload: CronScheduleUpdate,
    uow: UowDep,
    _admin: AdminUser,
) -> CronScheduleOut:
    service = CronSchedulerService(uow)
    return await service.update_schedule(schedule_id, payload)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int, uow: UowDep, _admin: AdminUser
) -> None:
    service = CronSchedulerService(uow)
    await service.delete_schedule(schedule_id)


@router.post("/{schedule_id}/enable", response_model=CronScheduleOut)
async def enable_schedule(
    schedule_id: int, uow: UowDep, _admin: AdminUser
) -> CronScheduleOut:
    service = CronSchedulerService(uow)
    return await service.enable_schedule(schedule_id)


@router.post("/{schedule_id}/disable", response_model=CronScheduleOut)
async def disable_schedule(
    schedule_id: int, uow: UowDep, _admin: AdminUser
) -> CronScheduleOut:
    service = CronSchedulerService(uow)
    return await service.disable_schedule(schedule_id)


@router.post("/{schedule_id}/trigger")
async def trigger_schedule(
    schedule_id: int, uow: UowDep, _admin: AdminUser
) -> dict[str, str]:
    service = CronSchedulerService(uow)
    return await service.trigger_schedule(schedule_id)
