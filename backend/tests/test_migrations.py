"""Database migration and schema smoke tests.

Because the real migrations target PostgreSQL (pgvector, TSVECTOR, custom
ENUMs), these tests run against the in-memory SQLite engine that the rest of
the test suite uses. The ``engine`` fixture already calls
``Base.metadata.create_all``, so the tests here verify that the table
structure produced by the ORM models is consistent with what the migrations
are expected to create.

For a production-grade CI pipeline you would run these tests against a real
PostgreSQL container. The tests are structured to be adapter-agnostic so they
can be promoted to full PG tests by swapping the engine fixture.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine


# ---------------------------------------------------------------------------
# Expected tables — everything in Base.metadata after the mocked models load.
# ---------------------------------------------------------------------------

EXPECTED_TABLES = {
    "users",
    "wishlists",
    "wishlist_items",
    "user_interactions",
    "items",
    "item_tags",
    "scraper_sites",
    "scraper_jobs",
    "cron_schedules",
    "instagram_queue",
    "ingestion_log",
    "review_queue",
    "recommendation_signals",
    "tag_types",
    "tags",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_expected_tables_exist(engine: AsyncEngine):
    """Every model table must be present after create_all."""
    def _get_tables(conn):
        inspector = inspect(conn)
        return set(inspector.get_table_names())

    async with engine.connect() as conn:
        tables = await conn.run_sync(_get_tables)

    missing = EXPECTED_TABLES - tables
    assert not missing, f"Tables missing from schema: {missing}"


@pytest.mark.asyncio
async def test_users_table_has_expected_columns(engine: AsyncEngine):
    """Spot-check that critical columns exist on the ``users`` table."""
    expected_cols = {
        "id", "email", "password_hash", "role", "display_name",
        "email_verified", "created_at", "updated_at",
    }

    def _get_cols(conn):
        inspector = inspect(conn)
        return {c["name"] for c in inspector.get_columns("users")}

    async with engine.connect() as conn:
        cols = await conn.run_sync(_get_cols)

    missing = expected_cols - cols
    assert not missing, f"Columns missing from users: {missing}"


@pytest.mark.asyncio
async def test_items_table_has_expected_columns(engine: AsyncEngine):
    expected_cols = {
        "id", "title", "description", "price", "currency",
        "source", "status", "content_hash", "view_count",
        "save_count", "click_count", "published_at",
    }

    def _get_cols(conn):
        inspector = inspect(conn)
        return {c["name"] for c in inspector.get_columns("items")}

    async with engine.connect() as conn:
        cols = await conn.run_sync(_get_cols)

    missing = expected_cols - cols
    assert not missing, f"Columns missing from items: {missing}"


@pytest.mark.asyncio
async def test_scraper_jobs_table_has_expected_columns(engine: AsyncEngine):
    expected_cols = {
        "id", "site_id", "status", "priority",
        "retry_count", "max_retries", "started_at", "completed_at",
    }

    def _get_cols(conn):
        inspector = inspect(conn)
        return {c["name"] for c in inspector.get_columns("scraper_jobs")}

    async with engine.connect() as conn:
        cols = await conn.run_sync(_get_cols)

    missing = expected_cols - cols
    assert not missing, f"Columns missing from scraper_jobs: {missing}"


@pytest.mark.asyncio
async def test_review_queue_table_has_expected_columns(engine: AsyncEngine):
    expected_cols = {"id", "item_id", "source", "priority", "created_at"}

    def _get_cols(conn):
        inspector = inspect(conn)
        return {c["name"] for c in inspector.get_columns("review_queue")}

    async with engine.connect() as conn:
        cols = await conn.run_sync(_get_cols)

    missing = expected_cols - cols
    assert not missing, f"Columns missing from review_queue: {missing}"


@pytest.mark.asyncio
async def test_tag_types_table_exists_with_required_columns(engine: AsyncEngine):
    expected_cols = {"id", "name", "is_filterable", "sort_order", "created_at"}

    def _get_cols(conn):
        inspector = inspect(conn)
        return {c["name"] for c in inspector.get_columns("tag_types")}

    async with engine.connect() as conn:
        cols = await conn.run_sync(_get_cols)

    missing = expected_cols - cols
    assert not missing, f"Columns missing from tag_types: {missing}"


@pytest.mark.asyncio
async def test_wishlist_items_unique_constraint_exists(engine: AsyncEngine):
    """The (wishlist_id, item_id) unique constraint must be present."""

    def _get_unique_constraints(conn):
        inspector = inspect(conn)
        constraints = inspector.get_unique_constraints("wishlist_items")
        return [c["column_names"] for c in constraints]

    async with engine.connect() as conn:
        uniques = await conn.run_sync(_get_unique_constraints)

    # Check that the wishlist_id+item_id pair is constrained.
    flat = [tuple(sorted(u)) for u in uniques]
    assert ("item_id", "wishlist_id") in flat, (
        f"Expected unique constraint on (wishlist_id, item_id), found: {uniques}"
    )


@pytest.mark.asyncio
async def test_can_insert_and_query_items_table(engine: AsyncEngine):
    """Sanity: raw SQL insert + select works against the bootstrapped schema."""
    import uuid as _uuid
    from datetime import datetime, timezone as _tz

    test_id = str(_uuid.uuid4())
    now = datetime.now(_tz.utc).isoformat()
    async with engine.begin() as conn:
        # Insert a minimal item row using raw SQL to bypass ORM layer.
        # We must supply id/created_at/updated_at explicitly because Python-side
        # ORM defaults don't fire for raw SQL executions on SQLite.
        await conn.execute(
            text(
                """
                INSERT INTO items
                    (id, title, source, status, currency, created_at, updated_at)
                VALUES
                    (:id, 'Migration Test Item', 'manual', 'pending_review', 'USD',
                     :now, :now)
                """
            ),
            {"id": test_id, "now": now},
        )
        result = await conn.execute(
            text("SELECT count(*) FROM items WHERE title = 'Migration Test Item'")
        )
        count = result.scalar_one()
        assert count >= 1

        # Clean up.
        await conn.execute(
            text("DELETE FROM items WHERE title = 'Migration Test Item'")
        )


@pytest.mark.asyncio
async def test_can_insert_and_query_tag_types(engine: AsyncEngine):
    """Seed tag_type rows can be inserted and retrieved."""
    from datetime import datetime, timezone as _tz

    now = datetime.now(_tz.utc).isoformat()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tag_types (name, is_filterable, sort_order, created_at) "
                "VALUES ('migration-test-type', 1, 0, :now)"
            ),
            {"now": now},
        )
        result = await conn.execute(
            text("SELECT name FROM tag_types WHERE name = 'migration-test-type'")
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "migration-test-type"

        # Clean up.
        await conn.execute(
            text("DELETE FROM tag_types WHERE name = 'migration-test-type'")
        )
