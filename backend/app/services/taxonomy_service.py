"""Tag taxonomy service: read tree + admin CRUD + tag merge."""

from __future__ import annotations

from sqlalchemy import delete, select, update

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.models.catalog import ItemTag
from app.models.taxonomy import Tag, TagType
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.taxonomy import (
    TagCreate,
    TagOut,
    TagTypeCreate,
    TagTypeOut,
    TagTypeUpdate,
    TagUpdate,
    TaxonomyTree,
)


# The taxonomy is hit on nearly every page — read-mostly with infrequent
# admin writes — so a 1-hour Redis cache is a high-leverage win. We invalidate
# explicitly on every mutation rather than relying on TTL alone so admin
# changes show up immediately.
TAXONOMY_CACHE_KEY = "taxonomy:filterable"
TAXONOMY_TTL_SECONDS = 3600

log = get_logger(__name__)


async def _invalidate_taxonomy_cache() -> None:
    try:
        redis = get_redis()
        await redis.delete(TAXONOMY_CACHE_KEY)
    except Exception:  # pragma: no cover - cache best-effort
        log.warning("taxonomy.cache.invalidate_failed", exc_info=True)


class TaxonomyService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ----------------------------------------------------------- read
    async def get_taxonomy(self) -> TaxonomyTree:
        # Hot path — try cache first, fall through to the DB on a miss or
        # any cache error. We never let a Redis hiccup take down taxonomy.
        try:
            redis = get_redis()
            cached = await redis.get(TAXONOMY_CACHE_KEY)
            if cached:
                return TaxonomyTree.model_validate_json(cached)
        except Exception:  # pragma: no cover - cache best-effort
            log.warning("taxonomy.cache.read_failed", exc_info=True)

        types = await self.uow.tags.get_filterable_taxonomy()
        tree = TaxonomyTree(
            types=[
                TagTypeOut(
                    id=t.id,
                    name=t.name,
                    description=t.description,
                    is_filterable=t.is_filterable,
                    sort_order=t.sort_order,
                    tags=[
                        TagOut(
                            id=tag.id,
                            tag_type_id=tag.tag_type_id,
                            name=tag.name,
                            slug=tag.slug,
                            parent_tag_id=tag.parent_tag_id,
                            sort_order=tag.sort_order,
                            is_active=tag.is_active,
                            tag_metadata=tag.tag_metadata,
                        )
                        for tag in t.tags
                    ],
                )
                for t in types
            ]
        )

        try:
            redis = get_redis()
            await redis.setex(
                TAXONOMY_CACHE_KEY,
                TAXONOMY_TTL_SECONDS,
                tree.model_dump_json(),
            )
        except Exception:  # pragma: no cover - cache best-effort
            log.warning("taxonomy.cache.write_failed", exc_info=True)

        return tree

    # -------------------------------------------------- TagType CRUD
    async def list_types(self) -> list[TagTypeOut]:
        types = await self.uow.tags.list_types()
        return [TagTypeOut.model_validate(t) for t in types]

    async def create_type(self, data: TagTypeCreate) -> TagTypeOut:
        existing = await self.uow.session.execute(
            select(TagType).where(TagType.name == data.name)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"TagType '{data.name}' already exists")
        tt = TagType(**data.model_dump())
        self.uow.session.add(tt)
        await self.uow.session.flush()
        await _invalidate_taxonomy_cache()
        return TagTypeOut.model_validate(tt)

    async def update_type(self, type_id: int, data: TagTypeUpdate) -> TagTypeOut:
        tt = await self.uow.session.get(TagType, type_id)
        if tt is None:
            raise NotFoundError(f"TagType {type_id} not found")
        changes = data.model_dump(exclude_unset=True)
        for k, v in changes.items():
            setattr(tt, k, v)
        await self.uow.session.flush()
        await _invalidate_taxonomy_cache()
        return TagTypeOut.model_validate(tt)

    async def delete_type(self, type_id: int) -> None:
        tt = await self.uow.session.get(TagType, type_id)
        if tt is None:
            raise NotFoundError(f"TagType {type_id} not found")
        # Refuse if any tags are attached — admin must merge/move them first.
        count = await self.uow.session.execute(
            select(Tag.id).where(Tag.tag_type_id == type_id).limit(1)
        )
        if count.scalar_one_or_none() is not None:
            raise ConflictError("Cannot delete a TagType that still has tags")
        await self.uow.session.delete(tt)
        await self.uow.session.flush()
        await _invalidate_taxonomy_cache()

    # ------------------------------------------------------ Tag CRUD
    async def create_tag(self, data: TagCreate) -> TagOut:
        # Verify tag_type exists.
        tt = await self.uow.session.get(TagType, data.tag_type_id)
        if tt is None:
            raise NotFoundError(f"TagType {data.tag_type_id} not found")
        # Slug uniqueness within the type.
        existing = await self.uow.tags.get_by_slug(tt.name, data.slug)
        if existing is not None:
            raise ConflictError(f"Tag '{data.slug}' already exists in '{tt.name}'")
        tag = Tag(**data.model_dump())
        self.uow.session.add(tag)
        await self.uow.session.flush()
        await _invalidate_taxonomy_cache()
        return TagOut.model_validate(tag)

    async def update_tag(self, tag_id: int, data: TagUpdate) -> TagOut:
        tag = await self.uow.session.get(Tag, tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")
        changes = data.model_dump(exclude_unset=True)
        for k, v in changes.items():
            setattr(tag, k, v)
        await self.uow.session.flush()
        await _invalidate_taxonomy_cache()
        return TagOut.model_validate(tag)

    async def delete_tag(self, tag_id: int) -> None:
        tag = await self.uow.session.get(Tag, tag_id)
        if tag is None:
            raise NotFoundError(f"Tag {tag_id} not found")
        await self.uow.session.delete(tag)
        await self.uow.session.flush()
        await _invalidate_taxonomy_cache()

    # ----------------------------------------------------------- merge
    async def merge_tags(self, source_id: int, target_id: int) -> int:
        """Migrate every item_tag from ``source_id`` to ``target_id``.

        Returns the number of item_tag rows that were migrated. The source
        tag is deleted on success. We use a single ON CONFLICT DO NOTHING
        update so items already tagged with the target are deduped.
        """
        if source_id == target_id:
            raise ValidationError("Source and target must differ")
        source = await self.uow.session.get(Tag, source_id)
        target = await self.uow.session.get(Tag, target_id)
        if source is None or target is None:
            raise NotFoundError("One or both tags do not exist")

        # Repoint item_tags. Two-step: update where target row doesn't already
        # exist, then delete leftover source rows.
        update_stmt = (
            update(ItemTag)
            .where(
                ItemTag.tag_id == source_id,
                ~ItemTag.item_id.in_(
                    select(ItemTag.item_id).where(ItemTag.tag_id == target_id)
                ),
            )
            .values(tag_id=target_id)
        )
        moved = (await self.uow.session.execute(update_stmt)).rowcount or 0

        await self.uow.session.execute(
            delete(ItemTag).where(ItemTag.tag_id == source_id)
        )
        await self.uow.session.delete(source)
        await self.uow.session.flush()
        await _invalidate_taxonomy_cache()
        return int(moved)
