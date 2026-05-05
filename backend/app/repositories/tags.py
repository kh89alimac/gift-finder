"""Tag taxonomy repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.taxonomy import Tag, TagType
from app.repositories.base import BaseRepository


class TagRepository(BaseRepository[Tag]):
    model = Tag

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Tag)

    async def get_by_type(self, tag_type_name: str) -> list[Tag]:
        """All active tags belonging to a tag type, ordered for UI display."""
        stmt = (
            select(Tag)
            .join(TagType, Tag.tag_type_id == TagType.id)
            .where(
                TagType.name == tag_type_name,
                Tag.is_active.is_(True),
            )
            .order_by(Tag.sort_order.asc(), Tag.name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_slug(self, tag_type_name: str, slug: str) -> Tag | None:
        """Find a tag by ``(tag_type.name, slug)``."""
        stmt = (
            select(Tag)
            .join(TagType, Tag.tag_type_id == TagType.id)
            .where(TagType.name == tag_type_name, Tag.slug == slug)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_filterable_taxonomy(self) -> list[TagType]:
        """Return all filterable tag types with their active tags eagerly loaded.

        This is what powers the discovery filter UI — one round trip yields
        the full taxonomy tree for client-side rendering.
        """
        stmt = (
            select(TagType)
            .where(TagType.is_filterable.is_(True))
            .order_by(TagType.sort_order.asc(), TagType.name.asc())
            .options(selectinload(TagType.tags))
        )
        result = await self.session.execute(stmt)
        # Filter out inactive tags after the load — we want every filterable
        # type even if it has zero active tags.
        types = list(result.scalars().all())
        for t in types:
            t.tags = [tag for tag in t.tags if tag.is_active]
            t.tags.sort(key=lambda tag: (tag.sort_order, tag.name))
        return types

    async def list_types(self) -> list[TagType]:
        """All tag types, ordered by sort_order."""
        stmt = select(TagType).order_by(TagType.sort_order.asc(), TagType.name.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
