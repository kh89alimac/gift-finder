"""Celery application factory.

Uses Redis as both broker and result backend (one less moving part to run).
celery-redbeat persists the schedule in Redis so beat can be restarted
without losing state — pair this with the ``cron_schedules`` admin table for
DB-managed schedules.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import settings


def _build_celery() -> Celery:
    broker = str(settings.REDIS_URL)
    backend = broker

    celery = Celery(
        "gift_finder",
        broker=broker,
        backend=backend,
        include=[
            "app.workers.tasks.scrape",
            "app.workers.tasks.embed",
            "app.workers.tasks.instagram",
            "app.workers.tasks.recommendations",
        ],
    )

    celery.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        task_time_limit=15 * 60,
        task_soft_time_limit=10 * 60,
        worker_max_tasks_per_child=200,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
        # celery-redbeat — DB-backed beat schedule.
        beat_scheduler="redbeat.RedBeatScheduler",
        redbeat_redis_url=broker,
        redbeat_lock_timeout=300,
        timezone="UTC",
        enable_utc=True,
    )

    return celery


celery_app = _build_celery()


# ---------------------------------------------------------------------------
# Helper to run async functions from inside sync Celery tasks
# ---------------------------------------------------------------------------


def run_async(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine from a sync Celery task.

    We avoid ``asyncio.run`` because long-lived workers may share a loop;
    this helper picks an existing loop if one is running.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Running inside an event loop already (rare for Celery, but handle it).
            future = asyncio.ensure_future(coro)
            return loop.run_until_complete(future)
    except RuntimeError:
        pass
    return asyncio.run(coro)
