"""Admin/internal models: ``review_queue``, ``recommendation_signals``."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import ENUM_TYPE_NAMES, ItemSource

if TYPE_CHECKING:
    from app.models.catalog import Item
    from app.models.taxonomy import Tag
    from app.models.user import User


_item_source_enum = PgEnum(
    ItemSource,
    name=ENUM_TYPE_NAMES[ItemSource],
    create_type=False,
    values_callable=lambda enum: [e.value for e in enum],
)


class ReviewQueue(Base):
    """Items needing admin review, optionally assigned to a specific moderator."""

    __tablename__ = "review_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    source: Mapped[ItemSource] = mapped_column(_item_source_enum, nullable=False)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(nullable=True)
    priority: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("5")
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("NOW()"), index=True
    )

    item: Mapped[Item] = relationship("Item", back_populates="review_queue_entry")
    assignee: Mapped[User | None] = relationship(
        "User", foreign_keys=[assigned_to], back_populates="review_assignments"
    )


class RecommendationSignal(Base):
    """Per-(user, tag) score used by the recommender. Composite PK."""

    __tablename__ = "recommendation_signals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    score: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default=text("0")
    )
    interaction_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("NOW()")
    )

    user: Mapped[User] = relationship("User", back_populates="recommendation_signals")
    tag: Mapped[Tag] = relationship("Tag")
