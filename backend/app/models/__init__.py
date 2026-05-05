"""SQLAlchemy ORM models.

Importing this package registers all models on the shared ``Base.metadata``,
which Alembic uses for autogenerate.
"""

from app.models.admin import RecommendationSignal, ReviewQueue
from app.models.base import Base, TimestampMixin
from app.models.catalog import Item, ItemTag, ScraperSite
from app.models.enums import (
    InstagramQueueStatus,
    InteractionType,
    ItemSource,
    ItemStatus,
    JobStatus,
    UserRole,
)
from app.models.ingestion import CronSchedule, IngestionLog, InstagramQueue, ScraperJob
from app.models.taxonomy import Tag, TagType
from app.models.user import User, UserInteraction, Wishlist, WishlistItem

__all__ = [
    "Base",
    "TimestampMixin",
    # enums
    "InstagramQueueStatus",
    "InteractionType",
    "ItemSource",
    "ItemStatus",
    "JobStatus",
    "UserRole",
    # taxonomy
    "Tag",
    "TagType",
    # catalog
    "Item",
    "ItemTag",
    "ScraperSite",
    # user
    "User",
    "UserInteraction",
    "Wishlist",
    "WishlistItem",
    # ingestion
    "CronSchedule",
    "IngestionLog",
    "InstagramQueue",
    "ScraperJob",
    # admin
    "RecommendationSignal",
    "ReviewQueue",
]
