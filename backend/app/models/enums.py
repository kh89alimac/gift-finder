"""Python enums that mirror the Postgres ENUM types.

Keep these in sync with ``001_initial_schema.py``. The string values are the
exact Postgres labels — SQLAlchemy will use them as-is.
"""

from __future__ import annotations

from enum import StrEnum


class ItemStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ItemSource(StrEnum):
    SCRAPER = "scraper"
    INSTAGRAM = "instagram"
    MANUAL = "manual"
    CSV_IMPORT = "csv_import"


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class InteractionType(StrEnum):
    VIEW = "view"
    CLICK = "click"
    SAVE = "save"
    REMOVE = "remove"
    SHARE = "share"
    PURCHASE = "purchase"
    DISMISS = "dismiss"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InstagramQueueStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


# Mapping from Python enum -> Postgres type name. Used by both the ORM column
# definitions and the migration so there is one source of truth.
ENUM_TYPE_NAMES: dict[type[StrEnum], str] = {
    ItemStatus: "item_status",
    ItemSource: "item_source",
    UserRole: "user_role",
    InteractionType: "interaction_type",
    JobStatus: "job_status",
    InstagramQueueStatus: "instagram_queue_status",
}
