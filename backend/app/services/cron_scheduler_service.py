"""CronSchedule admin service.

Wraps the ``cron_schedules`` table and dispatches manual runs to Celery.

For automatic runs we expect celery-redbeat (or similar) to read the table
and create scheduled task entries — the service itself doesn't poll, it just
owns the persistence + manual-trigger surface area.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.ingestion import CronSchedule
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.cron import CronScheduleIn, CronScheduleOut, CronScheduleUpdate
from app.workers.celery_app import celery_app

log = get_logger(__name__)


# Allowlist of fully-qualified Celery task names that admins are permitted to
# schedule. Anything else is rejected up-front so a compromised admin account
# can't schedule arbitrary code by guessing module paths.
ALLOWED_TASK_NAMES: frozenset[str] = frozenset(
    {
        "app.workers.tasks.scrape.scrape_site_task",
        "app.workers.tasks.embed.embed_item_task",
        "app.workers.tasks.instagram.instagram_fetch_task",
        "app.workers.tasks.recommendations.compute_recommendations_task",
    }
)


def _validate_task_name(task_name: str) -> None:
    if task_name not in ALLOWED_TASK_NAMES:
        raise ValidationError(
            f"task_name must be one of: {', '.join(sorted(ALLOWED_TASK_NAMES))}"
        )


class CronSchedulerService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # --------------------------------------------------------- list
    async def list_schedules(self) -> list[CronScheduleOut]:
        result = await self.uow.session.execute(
            select(CronSchedule).order_by(CronSchedule.name.asc())
        )
        return [CronScheduleOut.model_validate(s) for s in result.scalars().all()]

    async def get(self, schedule_id: int) -> CronScheduleOut:
        sched = await self.uow.session.get(CronSchedule, schedule_id)
        if sched is None:
            raise NotFoundError(f"CronSchedule {schedule_id} not found")
        return CronScheduleOut.model_validate(sched)

    # ------------------------------------------------------- create
    async def create_schedule(self, data: CronScheduleIn) -> CronScheduleOut:
        _validate_task_name(data.task_name)
        existing = await self.uow.session.execute(
            select(CronSchedule).where(CronSchedule.name == data.name)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"Schedule '{data.name}' already exists")
        sched = CronSchedule(**data.model_dump())
        self.uow.session.add(sched)
        await self.uow.session.flush()
        return CronScheduleOut.model_validate(sched)

    # ------------------------------------------------------- update
    async def update_schedule(
        self, schedule_id: int, data: CronScheduleUpdate
    ) -> CronScheduleOut:
        sched = await self.uow.session.get(CronSchedule, schedule_id)
        if sched is None:
            raise NotFoundError(f"CronSchedule {schedule_id} not found")
        changes = data.model_dump(exclude_unset=True)
        if "task_name" in changes and changes["task_name"] is not None:
            _validate_task_name(changes["task_name"])
        for k, v in changes.items():
            setattr(sched, k, v)
        await self.uow.session.flush()
        return CronScheduleOut.model_validate(sched)

    # ------------------------------------------------------- delete
    async def delete_schedule(self, schedule_id: int) -> None:
        sched = await self.uow.session.get(CronSchedule, schedule_id)
        if sched is None:
            raise NotFoundError(f"CronSchedule {schedule_id} not found")
        await self.uow.session.delete(sched)
        await self.uow.session.flush()

    # --------------------------------------------------- enable/disable
    async def enable_schedule(self, schedule_id: int) -> CronScheduleOut:
        return await self._set_active(schedule_id, True)

    async def disable_schedule(self, schedule_id: int) -> CronScheduleOut:
        return await self._set_active(schedule_id, False)

    async def _set_active(self, schedule_id: int, active: bool) -> CronScheduleOut:
        sched = await self.uow.session.get(CronSchedule, schedule_id)
        if sched is None:
            raise NotFoundError(f"CronSchedule {schedule_id} not found")
        sched.is_active = active
        await self.uow.session.flush()
        return CronScheduleOut.model_validate(sched)

    # ------------------------------------------------------- trigger
    async def trigger_schedule(self, schedule_id: int) -> dict[str, str]:
        """Manually fire the underlying Celery task. Returns ``{task_id: ...}``."""
        sched = await self.uow.session.get(CronSchedule, schedule_id)
        if sched is None:
            raise NotFoundError(f"CronSchedule {schedule_id} not found")

        # Resolve the task name through Celery's already-loaded task registry
        # rather than ``importlib`` — guarantees we never execute arbitrary
        # importable code, only registered Celery tasks.
        _validate_task_name(sched.task_name)
        task_fn = celery_app.tasks.get(sched.task_name)
        if task_fn is None:
            log.error("cron.trigger.unregistered", task=sched.task_name)
            raise ValidationError("Task not registered")

        try:
            async_result = task_fn.apply_async(kwargs=sched.task_kwargs)
        except Exception as exc:  # pragma: no cover - depends on broker
            log.error("cron.trigger.dispatch_failed", error=str(exc))
            raise ValidationError(f"Failed to dispatch task: {exc}") from exc

        sched.last_run_at = datetime.now(timezone.utc)
        await self.uow.session.flush()
        return {"task_id": str(async_result.id)}
