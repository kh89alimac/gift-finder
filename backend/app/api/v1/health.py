"""Health check endpoint with dependency diagnostics."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.logging import get_logger

router = APIRouter(tags=["health"])
log = get_logger(__name__)


class HealthCheckResponse(BaseModel):
    """Health check response with component status."""

    status: str  # "healthy" | "degraded"
    checks: dict[str, bool]  # component_name -> is_healthy


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthCheckResponse:
    """
    Health check endpoint.

    Returns status="healthy" only if both database and Redis are responding.
    Returns status="degraded" if any dependency is unreachable.
    """
    checks = {"database": False, "redis": False}

    # Check database connectivity
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        log.warning("health.check.database.failed", error=str(e))

    # Check Redis connectivity
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = True
    except Exception as e:
        log.warning("health.check.redis.failed", error=str(e))

    status = "healthy" if all(checks.values()) else "degraded"

    return HealthCheckResponse(status=status, checks=checks)
