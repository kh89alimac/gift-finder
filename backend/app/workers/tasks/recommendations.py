"""Recommendation recompute task."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.logging import get_logger
from app.repositories.unit_of_work import UnitOfWork
from app.services.recommendation_service import RecommendationService
from app.workers.celery_app import celery_app, run_async

log = get_logger("worker.recs")


@celery_app.task(
    name="app.workers.tasks.recommendations.compute_recommendations_task",
    bind=True,
)
def compute_recommendations_task(self: Any, user_id: str) -> bool:
    user_uuid = uuid.UUID(user_id)

    async def _run() -> bool:
        async with UnitOfWork() as uow:
            service = RecommendationService(uow)
            await service.compute_for_user(user_uuid)
            await uow.commit()
            return True

    return run_async(_run())
