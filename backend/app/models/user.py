"""User-facing models: ``users``, ``wishlists``, ``wishlist_items``, ``user_interactions``."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    Boolean,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ENUM_TYPE_NAMES, InteractionType, UserRole

if TYPE_CHECKING:
    from app.models.admin import RecommendationSignal, ReviewQueue
    from app.models.catalog import Item
    from app.models.ingestion import InstagramQueue


_user_role_enum = PgEnum(
    UserRole,
    name=ENUM_TYPE_NAMES[UserRole],
    create_type=False,
    values_callable=lambda enum: [e.value for e in enum],
)
_interaction_type_enum = PgEnum(
    InteractionType,
    name=ENUM_TYPE_NAMES[InteractionType],
    create_type=False,
    values_callable=lambda enum: [e.value for e in enum],
)


class User(Base, TimestampMixin):
    """An end-user or admin account."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        _user_role_enum,
        nullable=False,
        server_default=text("'user'::user_role"),
    )
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_s3_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oauth_provider_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'USD'")
    )
    onboarding_done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    wishlists: Mapped[list[Wishlist]] = relationship(
        "Wishlist",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    interactions: Mapped[list[UserInteraction]] = relationship(
        "UserInteraction",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reviewed_items: Mapped[list[Item]] = relationship(
        "Item",
        foreign_keys="Item.reviewed_by",
        back_populates="reviewer",
    )
    instagram_reviews: Mapped[list[InstagramQueue]] = relationship(
        "InstagramQueue",
        foreign_keys="InstagramQueue.reviewed_by",
        back_populates="reviewer",
    )
    review_assignments: Mapped[list[ReviewQueue]] = relationship(
        "ReviewQueue",
        foreign_keys="ReviewQueue.assigned_to",
        back_populates="assignee",
    )
    recommendation_signals: Mapped[list[RecommendationSignal]] = relationship(
        "RecommendationSignal",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"


class Wishlist(Base, TimestampMixin):
    """A user's named collection of saved items."""

    __tablename__ = "wishlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    share_token: Mapped[str | None] = mapped_column(
        String(32), unique=True, nullable=True
    )

    user: Mapped[User] = relationship("User", back_populates="wishlists")
    items: Mapped[list[WishlistItem]] = relationship(
        "WishlistItem",
        back_populates="wishlist",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WishlistItem.added_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Wishlist id={self.id} user={self.user_id} name={self.name!r}>"


class WishlistItem(Base):
    """An item saved to a wishlist with per-row metadata."""

    __tablename__ = "wishlist_items"
    __table_args__ = (
        UniqueConstraint(
            "wishlist_id", "item_id", name="uq_wishlist_items_wishlist_id_item_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    wishlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wishlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'normal'")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_purchased: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    added_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("NOW()")
    )

    wishlist: Mapped[Wishlist] = relationship("Wishlist", back_populates="items")
    item: Mapped[Item] = relationship("Item", back_populates="wishlist_items")


class UserInteraction(Base):
    """A single user-item interaction event used for recommendations & analytics."""

    __tablename__ = "user_interactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interaction_type: Mapped[InteractionType] = mapped_column(
        _interaction_type_enum, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("NOW()"), index=True
    )

    user: Mapped[User] = relationship("User", back_populates="interactions")
    item: Mapped[Item] = relationship("Item", back_populates="interactions")
