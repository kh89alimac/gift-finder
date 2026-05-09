"""Item repository: discovery, search, and ingestion-side upserts.

The discovery feed is the most performance-critical query in the app, so this
file is intentionally thorough about indexes and query shapes:

* ``search_by_profile`` uses tag-set intersection with cursor pagination on
  ``(published_at DESC, id DESC)`` so the keyset stays unique even when many
  items share a publish timestamp.
* ``fulltext_search`` uses the GIN index on the ``search_tsv`` column.
* ``vector_search`` uses the IVFFlat index on ``embedding`` (cosine distance).
* ``upsert_from_scrape`` relies on the partial unique index on
  ``(source_site_id, source_external_id)`` for idempotent ingestion.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, NamedTuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.safe_http import validate_display_url
from app.models.catalog import Item, ItemTag
from app.models.enums import ItemStatus
from app.repositories.base import BaseRepository


class ItemPageCursor(NamedTuple):
    """Opaque keyset cursor: serialize to base64 at the API boundary."""

    published_at: datetime | None
    id: uuid.UUID


class ItemRepository(BaseRepository[Item]):
    model = Item

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Item)

    async def get_by_id(self, id_: Any) -> Item | None:
        """Fetch an Item by PK with tags eagerly loaded."""
        stmt = (
            select(Item)
            .where(Item.id == id_)
            .options(selectinload(Item.tags))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # --------------------------------------------------------- discovery
    async def search_by_profile(
        self,
        *,
        tag_ids: Sequence[int] | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        sort: str = "relevance",
        limit: int = 24,
        cursor: ItemPageCursor | None = None,
        require_all_tags: bool = False,
    ) -> list[Item]:
        """Return active items matching a user profile.

        ``tag_ids`` selects items tagged with *any* of the given tags by
        default; pass ``require_all_tags=True`` to require all of them
        (intersection — useful when filters narrow rather than broaden).

        Pagination is keyset-based on ``(published_at, id)`` so it stays
        consistent under concurrent inserts and is O(1) regardless of page
        depth.
        """
        stmt = select(Item).where(Item.status == ItemStatus.ACTIVE)

        # Tag filter
        if tag_ids:
            if require_all_tags:
                # All tags must match — group by item, count distinct matches.
                tag_count = len(set(tag_ids))
                subq = (
                    select(ItemTag.item_id)
                    .where(ItemTag.tag_id.in_(tag_ids))
                    .group_by(ItemTag.item_id)
                    .having(func.count(func.distinct(ItemTag.tag_id)) == tag_count)
                    .subquery()
                )
                stmt = stmt.where(Item.id.in_(select(subq.c.item_id)))
            else:
                # Any tag matches.
                stmt = stmt.where(
                    Item.id.in_(
                        select(ItemTag.item_id).where(ItemTag.tag_id.in_(tag_ids))
                    )
                )

        # Price filter
        if price_min is not None:
            stmt = stmt.where(Item.price >= price_min)
        if price_max is not None:
            stmt = stmt.where(Item.price <= price_max)

        # Keyset cursor — strict tuple comparison handles ties on published_at.
        if cursor is not None:
            stmt = stmt.where(
                or_(
                    Item.published_at < cursor.published_at,
                    and_(
                        Item.published_at == cursor.published_at,
                        Item.id < cursor.id,
                    ),
                )
            )

        if sort == "price_asc":
            stmt = stmt.order_by(Item.price.asc().nulls_last(), Item.id.desc())
        elif sort == "price_desc":
            stmt = stmt.order_by(Item.price.desc().nulls_last(), Item.id.desc())
        elif sort == "popular":
            stmt = stmt.order_by(
                (Item.view_count + Item.save_count * 2 + Item.click_count).desc(),
                Item.id.desc(),
            )
        else:
            stmt = stmt.order_by(Item.published_at.desc().nulls_last(), Item.id.desc())

        stmt = stmt.limit(limit).options(selectinload(Item.tags))

        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    # ------------------------------------------------------------ search
    async def fulltext_search(
        self,
        query: str,
        *,
        limit: int = 24,
        only_active: bool = True,
    ) -> list[Item]:
        """Run a tsvector full-text search.

        Uses ``websearch_to_tsquery`` so users can write Google-style queries
        with quotes, ``OR``, and ``-exclusion`` natively.
        """
        ts_query = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank_cd(Item.search_tsv, ts_query)

        stmt = select(Item).where(Item.search_tsv.op("@@")(ts_query))
        if only_active:
            stmt = stmt.where(Item.status == ItemStatus.ACTIVE)

        stmt = stmt.order_by(rank.desc(), Item.published_at.desc().nulls_last()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ----------------------------------------------------------- vector
    async def vector_search(
        self,
        embedding: Sequence[float],
        *,
        limit: int = 24,
        tag_ids_filter: Sequence[int] | None = None,
        max_distance: float | None = None,
    ) -> list[tuple[Item, float]]:
        """Find items semantically nearest to ``embedding`` (cosine distance).

        Returns (item, distance) tuples ordered by ascending distance — i.e.
        most similar first. ``max_distance`` lets callers drop weak matches
        instead of always returning ``limit`` rows.
        """
        # pgvector cosine distance operator is <=> ; smaller is more similar.
        distance = Item.embedding.op("<=>")(embedding).label("distance")

        stmt = select(Item, distance).where(
            Item.status == ItemStatus.ACTIVE,
            Item.embedding.is_not(None),
        )

        if tag_ids_filter:
            stmt = stmt.where(
                Item.id.in_(
                    select(ItemTag.item_id).where(ItemTag.tag_id.in_(tag_ids_filter))
                )
            )

        if max_distance is not None:
            stmt = stmt.where(distance <= max_distance)

        stmt = stmt.order_by(distance.asc()).limit(limit)

        result = await self.session.execute(stmt)
        return [(row.Item, float(row.distance)) for row in result.all()]

    # ------------------------------------------------------------ dedup
    async def get_by_content_hash(self, content_hash: str) -> Item | None:
        """Return the item with the given content hash, if any."""
        stmt = select(Item).where(Item.content_hash == content_hash).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_source(
        self, source_site_id: int | None, source_external_id: str
    ) -> Item | None:
        """Look up an item by its (site, external_id) tuple."""
        stmt = select(Item).where(
            Item.source_site_id == source_site_id,
            Item.source_external_id == source_external_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ---------------------------------------------------------- upsert
    async def upsert_from_scrape(self, data: dict[str, Any]) -> tuple[Item, bool]:
        """INSERT ON CONFLICT DO UPDATE on the (site, external_id) unique index.

        Returns a tuple ``(item, created)`` where ``created`` is True if a new
        row was inserted, False if an existing row was updated. This is the
        single canonical entry point for scraper output — any other path risks
        duplicates.

        ``data`` must include ``source``, ``source_site_id``, ``source_external_id``
        and ``title``; all other columns are optional.
        """
        for required in ("source", "source_site_id", "source_external_id", "title"):
            if required not in data:
                raise ValueError(f"upsert_from_scrape missing required field: {required}")

        # Strip any javascript: / data: / file: URLs that a malicious scrape
        # could surface — the frontend renders these as <a href> targets.
        if "product_url" in data:
            data["product_url"] = validate_display_url(data.get("product_url"))
        if "image_url" in data:
            data["image_url"] = validate_display_url(data.get("image_url"))

        # Columns we want to refresh on conflict — explicitly enumerated to
        # avoid accidentally clobbering things like ``status`` or counters.
        refreshable = {
            "title",
            "description",
            "price",
            "currency",
            "image_url",
            "image_s3_key",
            "product_url",
            "brand",
            "retailer",
            "source_url",
            "content_hash",
            "embedding",
        }
        update_set = {k: v for k, v in data.items() if k in refreshable}
        # Always bump updated_at on conflict.
        update_set["updated_at"] = func.now()

        stmt = pg_insert(Item).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_items_source_site_id_source_external_id",
            set_=update_set,
        ).returning(Item, (stmt.excluded.id == Item.id).label("existed"))

        # Use ORM-aware execution to get a populated ``Item`` instance back.
        # We can't easily detect "created vs updated" in a single round trip
        # without xmax tricks, so do a follow-up check on the row's audit
        # timestamps as a heuristic (created if created_at == updated_at).
        result = await self.session.execute(
            pg_insert(Item)
            .values(**data)
            .on_conflict_do_update(
                constraint="uq_items_source_site_id_source_external_id",
                set_=update_set,
            )
            .returning(Item.id, Item.created_at, Item.updated_at)
        )
        row = result.one()
        item = await self.get_by_id_or_raise(row.id)
        created = row.created_at == row.updated_at
        return item, created

    # ------------------------------------------------------- counters
    async def increment_counter(
        self,
        item_id: uuid.UUID,
        counter: str,
        amount: int = 1,
    ) -> None:
        """Atomically bump one of ``view_count``, ``save_count``, ``click_count``."""
        if counter not in {"view_count", "save_count", "click_count"}:
            raise ValueError(f"Unknown counter column: {counter}")
        column = getattr(Item, counter)
        stmt = (
            Item.__table__.update()
            .where(Item.id == item_id)
            .values({counter: column + amount, "updated_at": func.now()})
        )
        await self.session.execute(stmt)

    # ------------------------------------------------------- moderation
    async def list_pending_review(self, *, limit: int = 50) -> list[Item]:
        """Return items awaiting moderator review, oldest first."""
        stmt = (
            select(Item)
            .where(Item.status == ItemStatus.PENDING_REVIEW)
            .order_by(Item.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
