"""Tag taxonomy: ``tag_types`` and ``tags`` tables.

A tag belongs to exactly one ``TagType`` (e.g. "interest", "occasion",
"recipient"). Tags are hierarchical via ``parent_tag_id`` so we can model
sub-categories without a separate join table.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.catalog import ItemTag


class TagType(Base):
    """A category of tags, e.g. ``interest``, ``occasion``, ``recipient``."""

    __tablename__ = "tag_types"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_filterable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("NOW()")
    )

    # Relationships
    tags: Mapped[list[Tag]] = relationship(
        "Tag",
        back_populates="tag_type",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TagType id={self.id} name={self.name!r}>"


class Tag(Base):
    """A single tag within a ``TagType``. May have a parent for hierarchy."""

    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("tag_type_id", "slug", name="uq_tags_tag_type_id_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag_type_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("tag_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_tag_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tags.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tag_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("NOW()")
    )

    # Relationships
    tag_type: Mapped[TagType] = relationship("TagType", back_populates="tags")
    parent: Mapped[Tag | None] = relationship(
        "Tag",
        remote_side="Tag.id",
        back_populates="children",
    )
    children: Mapped[list[Tag]] = relationship(
        "Tag",
        back_populates="parent",
    )
    item_tags: Mapped[list[ItemTag]] = relationship(
        "ItemTag",
        back_populates="tag",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Tag id={self.id} type={self.tag_type_id} slug={self.slug!r}>"
