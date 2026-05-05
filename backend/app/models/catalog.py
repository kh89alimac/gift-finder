"""Catalog models: ``items``, ``item_tags``, ``scraper_sites``.

The ``Item`` model is the heart of the catalog. It's deliberately denormalized
(brand/retailer as text, embedding inline) for read performance — discovery is
read-heavy and we want to avoid joins on the hot path.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CHAR,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ENUM_TYPE_NAMES, ItemSource, ItemStatus

if TYPE_CHECKING:
    from app.models.admin import RecommendationSignal, ReviewQueue
    from app.models.ingestion import InstagramQueue, ScraperJob
    from app.models.taxonomy import Tag
    from app.models.user import User, UserInteraction, WishlistItem


# Reuse ENUM types created by the migration. ``create_type=False`` tells
# SQLAlchemy not to try to issue another CREATE TYPE on metadata.create_all.
_item_status_enum = PgEnum(
    ItemStatus,
    name=ENUM_TYPE_NAMES[ItemStatus],
    create_type=False,
    values_callable=lambda enum: [e.value for e in enum],
)
_item_source_enum = PgEnum(
    ItemSource,
    name=ENUM_TYPE_NAMES[ItemSource],
    create_type=False,
    values_callable=lambda enum: [e.value for e in enum],
)


class ScraperSite(Base, TimestampMixin):
    """A retailer site we scrape, with its adapter and rate-limit config."""

    __tablename__ = "scraper_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    adapter_class: Mapped[str] = mapped_column(String(200), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )
    rate_limit_rps: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("1.0")
    )

    # Relationships
    items: Mapped[list[Item]] = relationship(
        "Item",
        back_populates="source_site",
        passive_deletes=True,
    )
    jobs: Mapped[list[ScraperJob]] = relationship(
        "ScraperJob",
        back_populates="site",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<ScraperSite id={self.id} name={self.name!r}>"


class Item(Base, TimestampMixin):
    """A giftable product. Created from scraping, IG approval, or manual entry."""

    __tablename__ = "items"
    __table_args__ = (
        # NULLS NOT DISTINCT means two rows with NULL source_site_id but the
        # same source_external_id still collide — we want that for true dedup.
        UniqueConstraint(
            "source_site_id",
            "source_external_id",
            name="uq_items_source_site_id_source_external_id",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_items_status_published_at", "status", "published_at"),
        Index("ix_items_brand", "brand"),
        Index("ix_items_retailer", "retailer"),
        Index("ix_items_content_hash", "content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Display fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'USD'")
    )
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_s3_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retailer: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Provenance
    source: Mapped[ItemSource] = mapped_column(_item_source_enum, nullable=False)
    source_site_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("scraper_sites.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lifecycle
    status: Mapped[ItemStatus] = mapped_column(
        _item_status_enum,
        nullable=False,
        server_default=text("'pending_review'::item_status"),
        index=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Search / recommendation
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    search_tsv: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)

    # Counters
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    save_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    click_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    published_at: Mapped[datetime | None] = mapped_column(nullable=True, index=True)

    # Relationships
    source_site: Mapped[ScraperSite | None] = relationship(
        "ScraperSite", back_populates="items"
    )
    reviewer: Mapped[User | None] = relationship(
        "User", foreign_keys=[reviewed_by], back_populates="reviewed_items"
    )
    item_tags: Mapped[list[ItemTag]] = relationship(
        "ItemTag",
        back_populates="item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tags: Mapped[list[Tag]] = relationship(
        "Tag",
        secondary="item_tags",
        viewonly=True,
        lazy="selectin",
    )
    wishlist_items: Mapped[list[WishlistItem]] = relationship(
        "WishlistItem",
        back_populates="item",
        passive_deletes=True,
    )
    interactions: Mapped[list[UserInteraction]] = relationship(
        "UserInteraction",
        back_populates="item",
        passive_deletes=True,
    )
    promoted_from_instagram: Mapped[list[InstagramQueue]] = relationship(
        "InstagramQueue",
        back_populates="promoted_item",
        passive_deletes=True,
    )
    review_queue_entry: Mapped[ReviewQueue | None] = relationship(
        "ReviewQueue",
        back_populates="item",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Item id={self.id} title={self.title!r} status={self.status}>"


class ItemTag(Base):
    """Many-to-many join between ``items`` and ``tags``."""

    __tablename__ = "item_tags"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )

    item: Mapped[Item] = relationship("Item", back_populates="item_tags")
    tag: Mapped[Tag] = relationship("Tag", back_populates="item_tags")
