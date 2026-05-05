"""Ingestion-side models: scraper jobs, cron schedules, IG queue, ingestion log."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, ENUM as PgEnum, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import (
    ENUM_TYPE_NAMES,
    InstagramQueueStatus,
    ItemSource,
    JobStatus,
)

if TYPE_CHECKING:
    from app.models.catalog import Item, ScraperSite
    from app.models.user import User


_job_status_enum = PgEnum(
    JobStatus,
    name=ENUM_TYPE_NAMES[JobStatus],
    create_type=False,
    values_callable=lambda enum: [e.value for e in enum],
)
_instagram_queue_status_enum = PgEnum(
    InstagramQueueStatus,
    name=ENUM_TYPE_NAMES[InstagramQueueStatus],
    create_type=False,
    values_callable=lambda enum: [e.value for e in enum],
)
_item_source_enum = PgEnum(
    ItemSource,
    name=ENUM_TYPE_NAMES[ItemSource],
    create_type=False,
    values_callable=lambda enum: [e.value for e in enum],
)


class CronSchedule(Base, TimestampMixin):
    """A recurring job definition used by the scheduler/worker."""

    __tablename__ = "cron_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    cron_expr: Mapped[str] = mapped_column(String(100), nullable=False)
    task_name: Mapped[str] = mapped_column(String(200), nullable=False)
    task_kwargs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )
    last_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(nullable=True, index=True)

    jobs: Mapped[list[ScraperJob]] = relationship(
        "ScraperJob",
        back_populates="schedule",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<CronSchedule id={self.id} name={self.name!r}>"


class ScraperJob(Base, TimestampMixin):
    """A unit of scraping work, claimed by workers via SKIP LOCKED."""

    __tablename__ = "scraper_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    site_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("scraper_sites.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    schedule_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("cron_schedules.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[JobStatus] = mapped_column(
        _job_status_enum,
        nullable=False,
        server_default=text("'queued'::job_status"),
        index=True,
    )
    priority: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("5")
    )
    items_found: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    items_created: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    items_updated: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    items_skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    max_retries: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("3")
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    site: Mapped[ScraperSite | None] = relationship("ScraperSite", back_populates="jobs")
    schedule: Mapped[CronSchedule | None] = relationship(
        "CronSchedule", back_populates="jobs"
    )
    log_entries: Mapped[list[IngestionLog]] = relationship(
        "IngestionLog",
        back_populates="job",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<ScraperJob id={self.id} site={self.site_id} status={self.status}>"


class InstagramQueue(Base, TimestampMixin):
    """Instagram posts awaiting admin review for promotion to items."""

    __tablename__ = "instagram_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    instagram_post_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    permalink: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_handle: Mapped[str] = mapped_column(String(100), nullable=False)
    hashtags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    suggested_tags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, server_default=text("0")
    )
    status: Mapped[InstagramQueueStatus] = mapped_column(
        _instagram_queue_status_enum,
        nullable=False,
        server_default=text("'pending'::instagram_queue_status"),
        index=True,
    )
    promoted_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    raw_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    promoted_item: Mapped[Item | None] = relationship(
        "Item", back_populates="promoted_from_instagram"
    )
    reviewer: Mapped[User | None] = relationship(
        "User", foreign_keys=[reviewed_by], back_populates="instagram_reviews"
    )

    def __repr__(self) -> str:
        return f"<InstagramQueue id={self.id} ig_id={self.instagram_post_id} status={self.status}>"


class IngestionLog(Base):
    """Append-only audit log of ingestion events."""

    __tablename__ = "ingestion_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scraper_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[ItemSource | None] = mapped_column(_item_source_enum, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    log_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("NOW()"), index=True
    )

    job: Mapped[ScraperJob | None] = relationship("ScraperJob", back_populates="log_entries")
