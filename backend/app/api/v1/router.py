"""Aggregate v1 router. Mounted on the FastAPI app under ``/api/v1``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth as auth_router
from app.api.v1 import health as health_router
from app.api.v1 import items as items_router
from app.api.v1 import recommendations as recommendations_router
from app.api.v1 import search as search_router
from app.api.v1 import wishlists as wishlists_router
from app.api.v1.admin import cron as admin_cron_router
from app.api.v1.admin import ingestion as admin_ingestion_router
from app.api.v1.admin import review_queue as admin_review_router
from app.api.v1.admin import taxonomy as admin_taxonomy_router

api_router = APIRouter()

# Health (should be first, no dependencies on other services for direct check)
api_router.include_router(health_router.router)

# Public-ish
api_router.include_router(auth_router.router)
api_router.include_router(items_router.router)
api_router.include_router(search_router.router)
api_router.include_router(wishlists_router.router)
api_router.include_router(recommendations_router.router)

# Admin
api_router.include_router(admin_review_router.router)
api_router.include_router(admin_taxonomy_router.router)
api_router.include_router(admin_cron_router.router)
api_router.include_router(admin_ingestion_router.router)
