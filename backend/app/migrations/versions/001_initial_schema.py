"""initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-05-03 00:00:00.000000

Creates the entire Gift Finder schema in one atomic migration:

- Postgres extensions (pgcrypto, pg_trgm, vector, btree_gist)
- ENUM types
- 15 tables in dependency order
- updated_at trigger function and triggers
- search_tsv trigger function and trigger on items
- All indexes (B-tree, GIN, IVFFlat, trigram, partial)
- Seed data for tag_types
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# Revision identifiers used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Enum definitions — must match app/models/enums.py exactly.
# ---------------------------------------------------------------------------

ITEM_STATUS_VALUES = ("pending_review", "active", "rejected", "archived")
ITEM_SOURCE_VALUES = ("scraper", "instagram", "manual", "csv_import")
USER_ROLE_VALUES = ("user", "admin")
INTERACTION_TYPE_VALUES = (
    "view",
    "click",
    "save",
    "remove",
    "share",
    "purchase",
    "dismiss",
)
JOB_STATUS_VALUES = ("queued", "running", "completed", "failed", "cancelled")
INSTAGRAM_QUEUE_STATUS_VALUES = ("pending", "approved", "rejected", "skipped")


def _enum(name: str, values: tuple[str, ...]) -> postgresql.ENUM:
    """Build a Postgres ENUM type bound to no metadata (we manage lifecycle)."""
    return postgresql.ENUM(*values, name=name, create_type=False)


# ---------------------------------------------------------------------------
# Triggers (created once, applied to every table that needs them)
# ---------------------------------------------------------------------------

UPDATED_AT_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

SEARCH_TSV_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION trg_items_update_search_tsv()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_tsv :=
        setweight(to_tsvector('english', coalesce(NEW.title, '')),       'A') ||
        setweight(to_tsvector('english', coalesce(NEW.brand, '')),       'B') ||
        setweight(to_tsvector('english', coalesce(NEW.retailer, '')),    'B') ||
        setweight(to_tsvector('english', coalesce(NEW.description, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# Tables that get an updated_at trigger.
UPDATED_AT_TABLES = (
    "scraper_sites",
    "items",
    "users",
    "wishlists",
    "scraper_jobs",
    "instagram_queue",
    "cron_schedules",
)


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

TAG_TYPES_SEED = [
    {
        "name": "interest",
        "description": "User interests and hobbies (e.g. cooking, gaming, photography)",
        "is_filterable": True,
        "sort_order": 10,
    },
    {
        "name": "occasion",
        "description": "Gift-giving occasions (e.g. birthday, wedding, holidays)",
        "is_filterable": True,
        "sort_order": 20,
    },
    {
        "name": "recipient",
        "description": "Who the gift is for (e.g. partner, parent, friend, child)",
        "is_filterable": True,
        "sort_order": 30,
    },
    {
        "name": "price_band",
        "description": "Price tier buckets (e.g. under-25, 25-50, 50-100, premium)",
        "is_filterable": True,
        "sort_order": 40,
    },
    {
        "name": "category",
        "description": "Product category taxonomy (e.g. electronics, apparel, home)",
        "is_filterable": True,
        "sort_order": 50,
    },
    {
        "name": "style",
        "description": "Aesthetic / personality vibe (e.g. minimalist, playful, luxe)",
        "is_filterable": True,
        "sort_order": 60,
    },
]


# ===========================================================================
# UPGRADE
# ===========================================================================


def upgrade() -> None:
    bind = op.get_bind()

    # --------------------------------------------------------- Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # ---------------------------------------------------------- Enum types
    item_status = postgresql.ENUM(*ITEM_STATUS_VALUES, name="item_status")
    item_status.create(bind, checkfirst=True)

    item_source = postgresql.ENUM(*ITEM_SOURCE_VALUES, name="item_source")
    item_source.create(bind, checkfirst=True)

    user_role = postgresql.ENUM(*USER_ROLE_VALUES, name="user_role")
    user_role.create(bind, checkfirst=True)

    interaction_type = postgresql.ENUM(
        *INTERACTION_TYPE_VALUES, name="interaction_type"
    )
    interaction_type.create(bind, checkfirst=True)

    job_status = postgresql.ENUM(*JOB_STATUS_VALUES, name="job_status")
    job_status.create(bind, checkfirst=True)

    instagram_queue_status = postgresql.ENUM(
        *INSTAGRAM_QUEUE_STATUS_VALUES, name="instagram_queue_status"
    )
    instagram_queue_status.create(bind, checkfirst=True)

    # ------------------------------------------------------------ Triggers
    op.execute(UPDATED_AT_FUNCTION_SQL)
    op.execute(SEARCH_TSV_FUNCTION_SQL)

    # =====================================================================
    # Tables — ordered so foreign keys always reference existing tables.
    # =====================================================================

    # ----------------------------------------------------------- tag_types
    op.create_table(
        "tag_types",
        sa.Column("id", sa.SmallInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_filterable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "sort_order",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # ---------------------------------------------------------------- tags
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tag_type_id",
            sa.SmallInteger(),
            sa.ForeignKey("tag_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column(
            "parent_tag_id",
            sa.Integer(),
            sa.ForeignKey("tags.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "sort_order",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("tag_type_id", "slug", name="uq_tags_tag_type_id_slug"),
    )
    op.create_index("ix_tags_tag_type_id", "tags", ["tag_type_id"])
    op.create_index("ix_tags_parent_tag_id", "tags", ["parent_tag_id"])

    # --------------------------------------------------------- scraper_sites
    op.create_table(
        "scraper_sites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("adapter_class", sa.String(200), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "rate_limit_rps",
            sa.Numeric(5, 2),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # --------------------------------------------------------------- users
    # Created before items because items.reviewed_by references users.id.
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column(
            "role",
            _enum("user_role", USER_ROLE_VALUES),
            nullable=False,
            server_default=sa.text("'user'::user_role"),
        ),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("avatar_s3_key", sa.Text(), nullable=True),
        sa.Column("oauth_provider", sa.String(50), nullable=True),
        sa.Column("oauth_provider_id", sa.Text(), nullable=True),
        sa.Column(
            "default_currency",
            sa.CHAR(3),
            nullable=False,
            server_default=sa.text("'USD'"),
        ),
        sa.Column(
            "onboarding_done",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_users_oauth_provider_provider_id",
        "users",
        ["oauth_provider", "oauth_provider_id"],
        unique=True,
        postgresql_where=sa.text("oauth_provider IS NOT NULL"),
    )

    # --------------------------------------------------------------- items
    op.create_table(
        "items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "currency",
            sa.CHAR(3),
            nullable=False,
            server_default=sa.text("'USD'"),
        ),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_s3_key", sa.Text(), nullable=True),
        sa.Column("product_url", sa.Text(), nullable=True),
        sa.Column("brand", sa.String(200), nullable=True),
        sa.Column("retailer", sa.String(200), nullable=True),
        sa.Column(
            "source",
            _enum("item_source", ITEM_SOURCE_VALUES),
            nullable=False,
        ),
        sa.Column(
            "source_site_id",
            sa.Integer(),
            sa.ForeignKey("scraper_sites.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_external_id", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "status",
            _enum("item_status", ITEM_STATUS_VALUES),
            nullable=False,
            server_default=sa.text("'pending_review'::item_status"),
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("search_tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column("content_hash", sa.CHAR(64), nullable=True),
        sa.Column(
            "view_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "save_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "click_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Unique with NULLS NOT DISTINCT so manual-source rows (NULL site_id)
    # still dedup on external id when one is provided.
    op.execute(
        """
        ALTER TABLE items
        ADD CONSTRAINT uq_items_source_site_id_source_external_id
        UNIQUE NULLS NOT DISTINCT (source_site_id, source_external_id);
        """
    )

    op.create_index("ix_items_status", "items", ["status"])
    op.create_index("ix_items_source_site_id", "items", ["source_site_id"])
    op.create_index("ix_items_published_at", "items", ["published_at"])
    op.create_index(
        "ix_items_status_published_at",
        "items",
        ["status", sa.text("published_at DESC NULLS LAST")],
    )
    op.create_index("ix_items_brand", "items", ["brand"])
    op.create_index("ix_items_retailer", "items", ["retailer"])
    op.create_index(
        "ix_items_content_hash",
        "items",
        ["content_hash"],
        postgresql_where=sa.text("content_hash IS NOT NULL"),
    )
    # GIN on the tsvector — full-text discovery search.
    op.create_index(
        "ix_items_search_tsv",
        "items",
        ["search_tsv"],
        postgresql_using="gin",
    )
    # Trigram index on title for ILIKE / similarity queries.
    op.create_index(
        "ix_items_title_trgm",
        "items",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    # IVFFlat index on the embedding column for ANN.
    # 100 lists is a reasonable starting point for ~100k–1M rows.
    op.execute(
        """
        CREATE INDEX ix_items_embedding_ivfflat
        ON items USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
        """
    )
    # Partial index for the "active feed" hot path.
    op.create_index(
        "ix_items_active_published",
        "items",
        [sa.text("published_at DESC NULLS LAST"), "id"],
        postgresql_where=sa.text("status = 'active'"),
    )

    # search_tsv trigger
    op.execute(
        """
        CREATE TRIGGER trg_items_search_tsv
        BEFORE INSERT OR UPDATE OF title, brand, retailer, description ON items
        FOR EACH ROW EXECUTE FUNCTION trg_items_update_search_tsv();
        """
    )

    # ------------------------------------------------------------ item_tags
    op.create_table(
        "item_tags",
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Integer(),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index("ix_item_tags_tag_id", "item_tags", ["tag_id"])
    op.create_index("ix_item_tags_item_id", "item_tags", ["item_id"])

    # ----------------------------------------------------------- wishlists
    op.create_table(
        "wishlists",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("share_token", sa.String(32), nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_wishlists_user_id", "wishlists", ["user_id"])

    # ------------------------------------------------------- wishlist_items
    op.create_table(
        "wishlist_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "wishlist_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wishlists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'normal'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_purchased",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "wishlist_id", "item_id", name="uq_wishlist_items_wishlist_id_item_id"
        ),
    )
    op.create_index("ix_wishlist_items_wishlist_id", "wishlist_items", ["wishlist_id"])
    op.create_index("ix_wishlist_items_item_id", "wishlist_items", ["item_id"])

    # ----------------------------------------------------- user_interactions
    op.create_table(
        "user_interactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "interaction_type",
            _enum("interaction_type", INTERACTION_TYPE_VALUES),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_user_interactions_user_id", "user_interactions", ["user_id"])
    op.create_index("ix_user_interactions_item_id", "user_interactions", ["item_id"])
    op.create_index(
        "ix_user_interactions_created_at", "user_interactions", ["created_at"]
    )
    op.create_index(
        "ix_user_interactions_user_type_created",
        "user_interactions",
        ["user_id", "interaction_type", sa.text("created_at DESC")],
    )

    # ------------------------------------------------------- cron_schedules
    op.create_table(
        "cron_schedules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("cron_expr", sa.String(100), nullable=False),
        sa.Column("task_name", sa.String(200), nullable=False),
        sa.Column(
            "task_kwargs",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_cron_schedules_next_run_at",
        "cron_schedules",
        ["next_run_at"],
        postgresql_where=sa.text("is_active = TRUE"),
    )

    # --------------------------------------------------------- scraper_jobs
    op.create_table(
        "scraper_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "site_id",
            sa.Integer(),
            sa.ForeignKey("scraper_sites.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "schedule_id",
            sa.Integer(),
            sa.ForeignKey("cron_schedules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            _enum("job_status", JOB_STATUS_VALUES),
            nullable=False,
            server_default=sa.text("'queued'::job_status"),
        ),
        sa.Column(
            "priority",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("5"),
        ),
        sa.Column(
            "items_found", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "items_created", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "items_updated", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "items_skipped", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "retry_count",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "max_retries",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_scraper_jobs_site_id", "scraper_jobs", ["site_id"])
    op.create_index("ix_scraper_jobs_status", "scraper_jobs", ["status"])
    # Hot index for the SKIP LOCKED claim query.
    op.create_index(
        "ix_scraper_jobs_queued_priority",
        "scraper_jobs",
        ["priority", "created_at"],
        postgresql_where=sa.text("status = 'queued'"),
    )

    # ----------------------------------------------------- instagram_queue
    op.create_table(
        "instagram_queue",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "instagram_post_id", sa.String(100), nullable=False, unique=True
        ),
        sa.Column("permalink", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("account_handle", sa.String(100), nullable=False),
        sa.Column(
            "hashtags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "suggested_tags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "confidence_score",
            sa.Numeric(5, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "status",
            _enum("instagram_queue_status", INSTAGRAM_QUEUE_STATUS_VALUES),
            nullable=False,
            server_default=sa.text("'pending'::instagram_queue_status"),
        ),
        sa.Column(
            "promoted_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "raw_data",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_instagram_queue_status", "instagram_queue", ["status"])
    op.create_index(
        "ix_instagram_queue_pending_score",
        "instagram_queue",
        [sa.text("confidence_score DESC"), "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    # GIN on hashtags for hashtag-based lookups.
    op.create_index(
        "ix_instagram_queue_hashtags",
        "instagram_queue",
        ["hashtags"],
        postgresql_using="gin",
    )

    # ------------------------------------------------------- ingestion_log
    op.create_table(
        "ingestion_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scraper_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source",
            _enum("item_source", ITEM_SOURCE_VALUES),
            nullable=True,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_ingestion_log_event_type", "ingestion_log", ["event_type"])
    op.create_index("ix_ingestion_log_job_id", "ingestion_log", ["job_id"])
    op.create_index("ix_ingestion_log_created_at", "ingestion_log", ["created_at"])

    # -------------------------------------------------------- review_queue
    op.create_table(
        "review_queue",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "source",
            _enum("item_source", ITEM_SOURCE_VALUES),
            nullable=False,
        ),
        sa.Column(
            "assigned_to",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "priority",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("5"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_review_queue_assigned_to", "review_queue", ["assigned_to"])
    op.create_index(
        "ix_review_queue_unassigned",
        "review_queue",
        ["priority", "created_at"],
        postgresql_where=sa.text("assigned_to IS NULL"),
    )

    # ----------------------------------------------- recommendation_signals
    op.create_table(
        "recommendation_signals",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Integer(),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "score",
            sa.Numeric(8, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "interaction_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_recommendation_signals_user_score",
        "recommendation_signals",
        ["user_id", sa.text("score DESC")],
    )

    # =====================================================================
    # updated_at triggers (only on tables that actually have updated_at)
    # =====================================================================
    for table in UPDATED_AT_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_set_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();
            """
        )

    # =====================================================================
    # Seed: tag_types
    # =====================================================================
    tag_types_table = sa.table(
        "tag_types",
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_filterable", sa.Boolean),
        sa.column("sort_order", sa.SmallInteger),
    )
    op.bulk_insert(tag_types_table, TAG_TYPES_SEED)


# ===========================================================================
# DOWNGRADE
# ===========================================================================


def downgrade() -> None:
    """Drop everything in reverse dependency order."""
    bind = op.get_bind()

    # Drop triggers (functions are dropped at the end).
    for table in UPDATED_AT_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_set_updated_at ON {table};")
    op.execute("DROP TRIGGER IF EXISTS trg_items_search_tsv ON items;")

    # Drop tables in reverse dependency order.
    op.drop_table("recommendation_signals")
    op.drop_table("review_queue")
    op.drop_table("ingestion_log")
    op.drop_table("instagram_queue")
    op.drop_table("scraper_jobs")
    op.drop_table("cron_schedules")
    op.drop_table("user_interactions")
    op.drop_table("wishlist_items")
    op.drop_table("wishlists")
    op.drop_table("item_tags")
    op.drop_table("items")
    op.drop_table("users")
    op.drop_table("scraper_sites")
    op.drop_table("tags")
    op.drop_table("tag_types")

    # Drop trigger functions.
    op.execute("DROP FUNCTION IF EXISTS trg_items_update_search_tsv();")
    op.execute("DROP FUNCTION IF EXISTS trg_set_updated_at();")

    # Drop ENUM types.
    for enum_name in (
        "instagram_queue_status",
        "job_status",
        "interaction_type",
        "user_role",
        "item_source",
        "item_status",
    ):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)

    # Note: extensions are intentionally NOT dropped — other databases or
    # schemas in the same cluster may depend on them.
