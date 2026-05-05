# Gift Finder App — PostgreSQL Database Design

## Table of Contents

1. [Entity Relationship Design](#1-entity-relationship-design)
2. [Schema Definitions (DDL)](#2-schema-definitions-ddl)
3. [Indexing Strategy](#3-indexing-strategy)
4. [Migration Strategy](#4-migration-strategy)
5. [Query Patterns](#5-query-patterns)
6. [Data Access Patterns](#6-data-access-patterns)

---

## 1. Entity Relationship Design

### Domain Groups

The schema is organized into five logical domains:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  TAXONOMY DOMAIN                                                                │
│  tag_types ──< tags                                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
         │
         │  (tags linked to items via item_tags)
         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  CATALOG DOMAIN                                                                 │
│  scraper_sites ──< items >── item_tags ──> tags                                 │
│                      │                                                          │
│                   (embedding stored in items.embedding via pgvector)            │
└─────────────────────────────────────────────────────────────────────────────────┘
         │
         │  (items saved to wishlists, interacted with by users)
         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  USER DOMAIN                                                                    │
│  users ──< wishlists ──< wishlist_items ──> items                               │
│    │                                                                            │
│    └──< user_interactions ──> items                                             │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  INGESTION DOMAIN                                                               │
│  cron_schedules ──< scraper_jobs ──> scraper_sites                              │
│  instagram_queue ──> items (on approval)                                        │
│  ingestion_log (append-only audit, references items / scraper_jobs)             │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  ADMIN DOMAIN                                                                   │
│  admin_users (subset of users with role='admin')                                │
│  review_queue ──> items  (items needing admin approval before going live)       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Table-by-Table Relationship Summary

| Table | Relates To | Cardinality | Notes |
|---|---|---|---|
| `tag_types` | `tags` | 1:N | One type (e.g. "occasion") owns many tags |
| `tags` | `items` | M:N via `item_tags` | |
| `scraper_sites` | `items` | 1:N | A site is the source for many items |
| `scraper_sites` | `scraper_jobs` | 1:N | A site has many job runs |
| `cron_schedules` | `scraper_jobs` | 1:N | A schedule fires many job runs |
| `items` | `wishlist_items` | 1:N | |
| `users` | `wishlists` | 1:N | |
| `wishlists` | `wishlist_items` | 1:N | |
| `users` | `user_interactions` | 1:N | |
| `items` | `user_interactions` | 1:N | |
| `instagram_queue` | `items` | 0..1:1 | After approval, promoted to items |
| `scraper_jobs` | `ingestion_log` | 1:N | |
| `items` | `ingestion_log` | 0..1:N | Optional — log entry may reference item |
| `items` | `review_queue` | 1:1 | Items that are `status='pending_review'` |

---

## 2. Schema Definitions (DDL)

### Extensions

```sql
-- Required extensions — run once on the database before migrations
CREATE EXTENSION IF NOT EXISTS "pgcrypto";       -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- trigram fuzzy text search
CREATE EXTENSION IF NOT EXISTS "vector";         -- pgvector for AI embeddings
CREATE EXTENSION IF NOT EXISTS "btree_gist";     -- GiST on btree-able types (numrange etc.)
```

---

### 2.1 Taxonomy Domain

```sql
-- ─────────────────────────────────────────────────────────────────────────────
-- tag_types: controlled vocabulary of tag dimensions
-- Examples: 'category', 'occasion', 'recipient_type', 'age_range',
--           'price_range', 'interest'
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE tag_types (
    id          SMALLSERIAL     PRIMARY KEY,
    name        VARCHAR(50)     NOT NULL UNIQUE,   -- e.g. 'occasion'
    description TEXT,
    is_filterable BOOLEAN       NOT NULL DEFAULT TRUE,  -- expose in filter UI
    sort_order  SMALLINT        NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Seed data (applied in initial migration):
-- INSERT INTO tag_types (name, description, sort_order) VALUES
--   ('category',       'Top-level product category',              1),
--   ('occasion',       'Gift-giving occasion',                    2),
--   ('recipient_type', 'Relationship to recipient',               3),
--   ('age_range',      'Target recipient age range',              4),
--   ('price_range',    'Price tier bucket',                       5),
--   ('interest',       'Recipient hobby / interest',              6);


-- ─────────────────────────────────────────────────────────────────────────────
-- tags: individual taxonomy values
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE tags (
    id              SERIAL          PRIMARY KEY,
    tag_type_id     SMALLINT        NOT NULL REFERENCES tag_types(id) ON DELETE RESTRICT,
    name            VARCHAR(100)    NOT NULL,           -- e.g. 'Birthday', 'Gardening'
    slug            VARCHAR(100)    NOT NULL,           -- url-safe, e.g. 'birthday'
    parent_tag_id   INT             REFERENCES tags(id) ON DELETE SET NULL,  -- optional hierarchy
    metadata        JSONB           NOT NULL DEFAULT '{}', -- e.g. {"min_age":0,"max_age":12} for age_range
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    sort_order      SMALLINT        NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_tags_type_slug UNIQUE (tag_type_id, slug)
);
```

---

### 2.2 Catalog Domain

```sql
-- ─────────────────────────────────────────────────────────────────────────────
-- scraper_sites: configuration record for each web source
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE scraper_sites (
    id              SERIAL          PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL UNIQUE,      -- 'Amazon', 'Etsy', ...
    base_url        TEXT            NOT NULL,
    adapter_class   VARCHAR(200)    NOT NULL,             -- Python dotted path to adapter
    config          JSONB           NOT NULL DEFAULT '{}',-- site-specific selectors/auth
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    rate_limit_rps  NUMERIC(5,2)    NOT NULL DEFAULT 1.0, -- requests per second
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);


-- ─────────────────────────────────────────────────────────────────────────────
-- items: unified gift catalog — core table
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE item_status   AS ENUM ('pending_review', 'active', 'rejected', 'archived');
CREATE TYPE item_source   AS ENUM ('scraper', 'instagram', 'manual', 'csv_import');

CREATE TABLE items (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core content
    title               VARCHAR(500)    NOT NULL,
    description         TEXT,
    price               NUMERIC(12, 2),                  -- NULL = price unknown
    currency            CHAR(3)         NOT NULL DEFAULT 'USD',
    image_url           TEXT,                            -- primary display image
    image_s3_key        TEXT,                            -- if we have a local copy in S3
    product_url         TEXT,                            -- affiliate / original link
    brand               VARCHAR(200),
    retailer            VARCHAR(200),

    -- Provenance
    source              item_source     NOT NULL,
    source_site_id      INT             REFERENCES scraper_sites(id) ON DELETE SET NULL,
    source_external_id  TEXT,                            -- external product id / SKU
    source_url          TEXT,

    -- Status & moderation
    status              item_status     NOT NULL DEFAULT 'pending_review',
    rejection_reason    TEXT,
    reviewed_by         UUID            REFERENCES users(id) ON DELETE SET NULL,  -- admin user
    reviewed_at         TIMESTAMPTZ,

    -- Search & AI
    -- 1536 dims = text-embedding-3-small; adjust to 3072 for text-embedding-3-large
    embedding           vector(1536),
    search_tsv          TSVECTOR,       -- full-text search vector (auto-updated via trigger)

    -- Deduplication
    content_hash        CHAR(64),       -- SHA-256 of (title + product_url) for dedup

    -- Metrics
    view_count          INT             NOT NULL DEFAULT 0,
    save_count          INT             NOT NULL DEFAULT 0,  -- denormalized for performance
    click_count         INT             NOT NULL DEFAULT 0,

    -- Audit
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    published_at        TIMESTAMPTZ,    -- set when status transitions to 'active'

    CONSTRAINT uq_items_source_external UNIQUE NULLS NOT DISTINCT (source_site_id, source_external_id)
);

-- Trigger: keep search_tsv up to date automatically
CREATE OR REPLACE FUNCTION items_search_tsv_update() RETURNS trigger AS $$
BEGIN
    NEW.search_tsv :=
        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(NEW.brand, '')), 'C') ||
        setweight(to_tsvector('english', coalesce(NEW.retailer, '')), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_items_search_tsv
    BEFORE INSERT OR UPDATE OF title, description, brand, retailer
    ON items
    FOR EACH ROW EXECUTE FUNCTION items_search_tsv_update();

-- Trigger: updated_at maintenance (reusable function)
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_items_updated_at
    BEFORE UPDATE ON items
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ─────────────────────────────────────────────────────────────────────────────
-- item_tags: many-to-many items <-> tags
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE item_tags (
    item_id     UUID        NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    tag_id      INT         NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (item_id, tag_id)
);
```

---

### 2.3 User Domain

```sql
-- ─────────────────────────────────────────────────────────────────────────────
-- users: authentication + profile
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE user_role AS ENUM ('user', 'admin');

CREATE TABLE users (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR(320)    NOT NULL UNIQUE,
    email_verified      BOOLEAN         NOT NULL DEFAULT FALSE,
    password_hash       TEXT,                            -- NULL if OAuth-only
    role                user_role       NOT NULL DEFAULT 'user',

    -- Profile
    display_name        VARCHAR(100),
    avatar_url          TEXT,
    avatar_s3_key       TEXT,

    -- OAuth tokens (stored encrypted at application layer)
    oauth_provider      VARCHAR(50),                     -- 'google', 'apple', etc.
    oauth_provider_id   TEXT,

    -- Preferences (denormalized for fast personalization reads)
    default_currency    CHAR(3)         NOT NULL DEFAULT 'USD',
    onboarding_done     BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Account state
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_users_oauth UNIQUE NULLS NOT DISTINCT (oauth_provider, oauth_provider_id)
);

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ─────────────────────────────────────────────────────────────────────────────
-- wishlists
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE wishlists (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(200)    NOT NULL DEFAULT 'My Wishlist',
    description     TEXT,
    share_token     VARCHAR(64)     UNIQUE,              -- non-null = public share link
    is_public       BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_wishlists_updated_at
    BEFORE UPDATE ON wishlists
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ─────────────────────────────────────────────────────────────────────────────
-- wishlist_items
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE wishlist_items (
    id              BIGSERIAL       PRIMARY KEY,
    wishlist_id     UUID            NOT NULL REFERENCES wishlists(id) ON DELETE CASCADE,
    item_id         UUID            NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    note            TEXT,                                -- personal note from user
    priority        SMALLINT        NOT NULL DEFAULT 0,  -- 0=normal, 1=high, 2=must-have
    is_purchased    BOOLEAN         NOT NULL DEFAULT FALSE,
    sort_order      INT             NOT NULL DEFAULT 0,
    added_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_wishlist_items UNIQUE (wishlist_id, item_id)
);


-- ─────────────────────────────────────────────────────────────────────────────
-- user_interactions: feed for the recommendation engine
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE interaction_type AS ENUM (
    'view',         -- item detail page viewed
    'click',        -- affiliate link clicked
    'save',         -- added to wishlist
    'remove',       -- removed from wishlist
    'share',        -- shared item
    'purchase',     -- confirmed purchase signal
    'dismiss'       -- user explicitly not interested
);

CREATE TABLE user_interactions (
    id              BIGSERIAL           PRIMARY KEY,
    user_id         UUID                NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id         UUID                NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    interaction     interaction_type    NOT NULL,
    session_id      VARCHAR(128),                    -- for anonymous / pre-login tracking
    metadata        JSONB               NOT NULL DEFAULT '{}',  -- e.g. {"source": "recommendation"}
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);
```

---

### 2.4 Ingestion Domain

```sql
-- ─────────────────────────────────────────────────────────────────────────────
-- cron_schedules: admin-configurable cron job definitions
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE schedule_status AS ENUM ('active', 'paused', 'deleted');

CREATE TABLE cron_schedules (
    id              SERIAL          PRIMARY KEY,
    name            VARCHAR(200)    NOT NULL UNIQUE,
    description     TEXT,
    cron_expression VARCHAR(100)    NOT NULL,             -- '0 */6 * * *'
    task_name       VARCHAR(200)    NOT NULL,             -- Celery/ARQ task dotted path
    task_kwargs     JSONB           NOT NULL DEFAULT '{}',
    status          schedule_status NOT NULL DEFAULT 'active',
    last_run_at     TIMESTAMPTZ,
    next_run_at     TIMESTAMPTZ,
    created_by      UUID            REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_cron_schedules_updated_at
    BEFORE UPDATE ON cron_schedules
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ─────────────────────────────────────────────────────────────────────────────
-- scraper_jobs: individual job run instances (job queue entries)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE job_status AS ENUM (
    'queued', 'running', 'completed', 'failed', 'cancelled'
);

CREATE TABLE scraper_jobs (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id             INT             NOT NULL REFERENCES scraper_sites(id) ON DELETE RESTRICT,
    schedule_id         INT             REFERENCES cron_schedules(id) ON DELETE SET NULL,
    triggered_by        UUID            REFERENCES users(id) ON DELETE SET NULL, -- NULL = cron
    celery_task_id      VARCHAR(255),                    -- Celery AsyncResult id

    status              job_status      NOT NULL DEFAULT 'queued',
    priority            SMALLINT        NOT NULL DEFAULT 5,  -- lower = higher priority

    -- Input parameters
    start_url           TEXT,
    scrape_params       JSONB           NOT NULL DEFAULT '{}',

    -- Runtime stats
    items_scraped       INT             NOT NULL DEFAULT 0,
    items_new           INT             NOT NULL DEFAULT 0,
    items_updated       INT             NOT NULL DEFAULT 0,
    items_duplicate     INT             NOT NULL DEFAULT 0,
    items_failed        INT             NOT NULL DEFAULT 0,

    error_message       TEXT,
    error_traceback     TEXT,

    queued_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,

    -- Retry tracking
    attempt_number      SMALLINT        NOT NULL DEFAULT 1,
    max_attempts        SMALLINT        NOT NULL DEFAULT 3
);


-- ─────────────────────────────────────────────────────────────────────────────
-- instagram_queue: raw Instagram posts pending review
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE instagram_status AS ENUM (
    'pending',      -- awaiting admin review
    'approved',     -- promoted to items table
    'rejected',     -- discarded
    'duplicate'     -- already exists in items
);

CREATE TABLE instagram_queue (
    id                  BIGSERIAL       PRIMARY KEY,
    instagram_media_id  VARCHAR(100)    NOT NULL UNIQUE,  -- Meta Graph API media id
    instagram_account   VARCHAR(100),                     -- source account handle
    hashtag             VARCHAR(100),                     -- source hashtag if applicable
    permalink           TEXT            NOT NULL,
    media_type          VARCHAR(20),                      -- 'IMAGE', 'VIDEO', 'CAROUSEL'
    media_url           TEXT,
    thumbnail_url       TEXT,
    caption             TEXT,
    raw_json            JSONB           NOT NULL DEFAULT '{}',  -- full API response
    status              instagram_status NOT NULL DEFAULT 'pending',

    -- Review
    reviewed_by         UUID            REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at         TIMESTAMPTZ,
    rejection_reason    TEXT,

    -- If approved, link to the resulting item
    item_id             UUID            REFERENCES items(id) ON DELETE SET NULL,

    -- Auto-classification attempt before review
    suggested_tags      INT[]           DEFAULT '{}',     -- array of tag ids from AI classification
    confidence_score    NUMERIC(4,3),                     -- 0.000 – 1.000

    fetched_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    posted_at           TIMESTAMPTZ                       -- original post timestamp from Instagram
);


-- ─────────────────────────────────────────────────────────────────────────────
-- ingestion_log: append-only audit trail for all ingestion activity
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE ingestion_event AS ENUM (
    'item_created',
    'item_updated',
    'item_duplicate_skipped',
    'item_rejected',
    'item_approved',
    'instagram_fetched',
    'scraper_started',
    'scraper_completed',
    'scraper_failed',
    'csv_import_started',
    'csv_import_completed',
    'manual_entry_created'
);

CREATE TABLE ingestion_log (
    id              BIGSERIAL           PRIMARY KEY,
    event           ingestion_event     NOT NULL,
    source          item_source         NOT NULL,
    job_id          UUID                REFERENCES scraper_jobs(id) ON DELETE SET NULL,
    item_id         UUID                REFERENCES items(id) ON DELETE SET NULL,
    instagram_id    BIGINT              REFERENCES instagram_queue(id) ON DELETE SET NULL,
    actor_user_id   UUID                REFERENCES users(id) ON DELETE SET NULL,
    details         JSONB               NOT NULL DEFAULT '{}',  -- event-specific payload
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);
-- Note: NO updated_at — this table is append-only by design.
-- Enforce at application layer; optionally add a rule:
-- CREATE RULE no_update_ingestion_log AS ON UPDATE TO ingestion_log DO INSTEAD NOTHING;
```

---

### 2.5 Review Queue Domain

```sql
-- ─────────────────────────────────────────────────────────────────────────────
-- review_queue: items awaiting admin approval (projection of items.status)
-- This table provides a fast, pageable queue without full table scans on items.
-- It is kept in sync with items via triggers.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE review_queue (
    id              BIGSERIAL       PRIMARY KEY,
    item_id         UUID            NOT NULL UNIQUE REFERENCES items(id) ON DELETE CASCADE,
    source          item_source     NOT NULL,
    priority        SMALLINT        NOT NULL DEFAULT 0,  -- admin can bump priority
    assigned_to     UUID            REFERENCES users(id) ON DELETE SET NULL,
    notes           TEXT,
    entered_queue_at TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- Trigger: auto-enqueue when item is created/updated to pending_review status
CREATE OR REPLACE FUNCTION sync_review_queue() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'pending_review' THEN
        INSERT INTO review_queue (item_id, source)
        VALUES (NEW.id, NEW.source)
        ON CONFLICT (item_id) DO NOTHING;
    ELSE
        DELETE FROM review_queue WHERE item_id = NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_items_review_queue
    AFTER INSERT OR UPDATE OF status
    ON items
    FOR EACH ROW EXECUTE FUNCTION sync_review_queue();
```

---

### 2.6 Recommendation Signals (Materialized)

```sql
-- ─────────────────────────────────────────────────────────────────────────────
-- recommendation_signals: pre-computed per-user affinity scores per tag
-- Populated/refreshed by a background job from user_interactions.
-- Used by the recommendation engine as a fast lookup.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE recommendation_signals (
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tag_id          INT         NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    score           NUMERIC(8,4) NOT NULL DEFAULT 0,  -- affinity score, higher = stronger
    interaction_count INT       NOT NULL DEFAULT 0,
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (user_id, tag_id)
);
```

---

## 3. Indexing Strategy

### 3.1 items table — the most performance-critical table

```sql
-- Status + published_at: primary listing query filter
CREATE INDEX idx_items_status_published
    ON items (status, published_at DESC)
    WHERE status = 'active';

-- Full-text search
CREATE INDEX idx_items_search_tsv
    ON items USING GIN (search_tsv);

-- AI semantic search (pgvector — IVFFlat for approximate nearest neighbor)
-- Build AFTER initial bulk load; lists=100 for ~1M rows
CREATE INDEX idx_items_embedding_ivfflat
    ON items USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Trigram index for fuzzy title search / autocomplete
CREATE INDEX idx_items_title_trgm
    ON items USING GIN (title gin_trgm_ops);

-- Source dedup lookup
CREATE INDEX idx_items_content_hash
    ON items (content_hash)
    WHERE content_hash IS NOT NULL;

-- Price range filter (used in gift-finder filters)
CREATE INDEX idx_items_price
    ON items (price)
    WHERE price IS NOT NULL AND status = 'active';

-- Source site provenance
CREATE INDEX idx_items_source_site
    ON items (source_site_id, created_at DESC)
    WHERE source_site_id IS NOT NULL;

-- Admin review queue support (items in pending state)
CREATE INDEX idx_items_status_pending
    ON items (created_at DESC)
    WHERE status = 'pending_review';
```

### 3.2 item_tags — bridge table

```sql
-- Forward lookup: tags on an item
CREATE INDEX idx_item_tags_item_id   ON item_tags (item_id);

-- Reverse lookup: all items for a tag (used heavily by filter queries)
CREATE INDEX idx_item_tags_tag_id    ON item_tags (tag_id);

-- Composite for "active items with this tag" — most common filter query
CREATE INDEX idx_item_tags_tag_active
    ON item_tags (tag_id, item_id);
-- Join with items WHERE status='active' covered by idx_items_status_published
```

### 3.3 tags table

```sql
CREATE INDEX idx_tags_type_id   ON tags (tag_type_id, sort_order);
CREATE INDEX idx_tags_slug      ON tags (slug);
CREATE INDEX idx_tags_active    ON tags (tag_type_id) WHERE is_active = TRUE;
```

### 3.4 users table

```sql
CREATE INDEX idx_users_email        ON users (email);         -- unique but explicit for clarity
CREATE INDEX idx_users_oauth        ON users (oauth_provider, oauth_provider_id)
    WHERE oauth_provider IS NOT NULL;
CREATE INDEX idx_users_active       ON users (created_at DESC) WHERE is_active = TRUE;
```

### 3.5 wishlists / wishlist_items

```sql
CREATE INDEX idx_wishlists_user_id      ON wishlists (user_id, created_at DESC);
CREATE INDEX idx_wishlists_share_token  ON wishlists (share_token) WHERE share_token IS NOT NULL;
CREATE INDEX idx_wishlist_items_wishlist ON wishlist_items (wishlist_id, sort_order);
CREATE INDEX idx_wishlist_items_item    ON wishlist_items (item_id);
```

### 3.6 user_interactions

```sql
-- Recommendation engine: interactions per user
CREATE INDEX idx_interactions_user_item
    ON user_interactions (user_id, interaction, created_at DESC);

-- Item-level engagement metrics
CREATE INDEX idx_interactions_item
    ON user_interactions (item_id, interaction);

-- Time-windowed queries (e.g., trending in last 7 days)
CREATE INDEX idx_interactions_created_at
    ON user_interactions (created_at DESC);
```

### 3.7 scraper_jobs

```sql
CREATE INDEX idx_scraper_jobs_status_queued
    ON scraper_jobs (priority, queued_at)
    WHERE status = 'queued';

CREATE INDEX idx_scraper_jobs_site_status
    ON scraper_jobs (site_id, status, queued_at DESC);

CREATE INDEX idx_scraper_jobs_celery_task
    ON scraper_jobs (celery_task_id)
    WHERE celery_task_id IS NOT NULL;
```

### 3.8 instagram_queue

```sql
CREATE INDEX idx_instagram_queue_status
    ON instagram_queue (status, fetched_at DESC)
    WHERE status = 'pending';

CREATE INDEX idx_instagram_queue_account
    ON instagram_queue (instagram_account, fetched_at DESC);
```

### 3.9 ingestion_log

```sql
-- Audit trail queries by job
CREATE INDEX idx_ingestion_log_job       ON ingestion_log (job_id, created_at DESC);
-- Audit trail by item
CREATE INDEX idx_ingestion_log_item      ON ingestion_log (item_id, created_at DESC);
-- Time-range audit queries
CREATE INDEX idx_ingestion_log_created   ON ingestion_log (created_at DESC);
-- Source-based reporting
CREATE INDEX idx_ingestion_log_event     ON ingestion_log (event, source, created_at DESC);
```

### 3.10 recommendation_signals

```sql
CREATE INDEX idx_rec_signals_user_score
    ON recommendation_signals (user_id, score DESC);
```

### 3.11 review_queue

```sql
CREATE INDEX idx_review_queue_priority
    ON review_queue (priority DESC, entered_queue_at ASC);
CREATE INDEX idx_review_queue_assigned
    ON review_queue (assigned_to) WHERE assigned_to IS NOT NULL;
```

---

## 4. Migration Strategy

### 4.1 Alembic Setup

```
alembic/
├── env.py               # async engine setup (asyncpg)
├── script.py.mako
└── versions/
    ├── 0001_initial_extensions.py
    ├── 0002_taxonomy.py
    ├── 0003_catalog_items.py
    ├── 0004_users.py
    ├── 0005_wishlists.py
    ├── 0006_ingestion.py
    ├── 0007_review_queue.py
    ├── 0008_recommendation.py
    └── 0009_indexes.py
```

**`alembic/env.py` (async pattern):**

```python
from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from app.db.base import Base  # imports all models

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"),
                      target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    connectable: AsyncEngine = create_async_engine(
        config.get_main_option("sqlalchemy.url")
    )
    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda conn: context.configure(
                connection=conn,
                target_metadata=target_metadata,
                compare_type=True,          # detect column type changes
                compare_server_default=True
            )
        )
        async with context.begin_transaction():
            await connection.run_sync(lambda _: context.run_migrations())
```

### 4.2 Migration Authoring Rules

1. **Every migration is reversible** — always implement `downgrade()`. Mark irreversible steps with a comment and raise `NotImplementedError` in `downgrade()` only for destructive data migrations.

2. **Zero-downtime column additions** — add columns as nullable first, backfill data in a separate migration, then add `NOT NULL` constraint in a third migration (using `ALTER TABLE ... SET NOT NULL` which in Postgres 12+ checks constraint without full rewrite for `CHECK (col IS NOT NULL)`).

   ```sql
   -- Step 1: add nullable
   ALTER TABLE items ADD COLUMN retailer_category VARCHAR(100);

   -- Step 2 (data migration, separate migration file):
   UPDATE items SET retailer_category = 'General' WHERE retailer_category IS NULL;

   -- Step 3: enforce NOT NULL via check constraint (fast, no rewrite in PG12+)
   ALTER TABLE items ADD CONSTRAINT chk_items_retailer_category_notnull
       CHECK (retailer_category IS NOT NULL) NOT VALID;
   ALTER TABLE items VALIDATE CONSTRAINT chk_items_retailer_category_notnull;
   ```

3. **Index creation** — always use `CREATE INDEX CONCURRENTLY` for large tables in production. Alembic does not support `CONCURRENTLY` natively; wrap in `op.execute()`:
   ```python
   op.execute(
       "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_items_price "
       "ON items(price) WHERE price IS NOT NULL AND status = 'active'"
   )
   ```
   Run in a separate migration that disables transactional DDL:
   ```python
   def upgrade():
       # Disable transactional DDL for CONCURRENTLY index creation
       connection = op.get_bind()
       connection.execute(text("COMMIT"))
       op.execute("CREATE INDEX CONCURRENTLY ...")
   ```

4. **Enum additions** — `ALTER TYPE ... ADD VALUE` is safe but cannot be rolled back. Always add new enum values; never remove. Mark deprecated values as such in documentation.

5. **pgvector index build** — build `ivfflat` index only after the table has significant data (at minimum 10× `lists` rows). Run as a separate post-migration step outside the migration file.

6. **Migration version naming convention:**
   ```
   YYYYMMDDHHMMSS_<short_description>.py
   ```
   Generated by: `alembic revision --autogenerate -m "add_retailer_category_to_items"`

7. **Pre-production checklist:**
   - Run `alembic check` in CI to detect model/migration drift
   - Test `downgrade` to previous version in staging
   - For large table changes, estimate duration using `pg_stat_progress_alter_table`
   - Lock timeout: set `lock_timeout = '2s'` at session level before DDL to avoid blocking long-running queries

---

## 5. Query Patterns

### QP-1: Gift Discovery — profile-based filter

**"Find active gifts for recipient: age 30, relationship=friend, occasion=birthday, budget=$50-$100"**

The filter is a multi-tag intersection. Tags for `age_range`, `recipient_type`, `occasion`, and `price_range` each have their own `tag_id` values.

```sql
SELECT i.id, i.title, i.price, i.image_url, i.product_url
FROM items i
WHERE i.status = 'active'
  AND i.price BETWEEN 50 AND 100
  AND EXISTS (
      SELECT 1 FROM item_tags it
      JOIN tags t ON t.id = it.tag_id
      WHERE it.item_id = i.id AND t.slug = 'birthday'
        AND t.tag_type_id = (SELECT id FROM tag_types WHERE name = 'occasion')
  )
  AND EXISTS (
      SELECT 1 FROM item_tags it
      JOIN tags t ON t.id = it.tag_id
      WHERE it.item_id = i.id AND t.slug = 'friend'
        AND t.tag_type_id = (SELECT id FROM tag_types WHERE name = 'recipient_type')
  )
ORDER BY i.save_count DESC, i.published_at DESC
LIMIT 24 OFFSET 0;
```

**Optimized version using array intersection (faster for many tags):**

```sql
-- Resolve tag ids once at application layer, pass as array
-- E.g. tag_ids = [birthday_id, friend_id, adult_id, mid_range_id]
SELECT i.id, i.title, i.price, i.image_url, i.product_url,
       COUNT(it.tag_id) AS matched_tags
FROM items i
JOIN item_tags it ON it.item_id = i.id AND it.tag_id = ANY(:tag_ids)
WHERE i.status = 'active'
  AND i.price BETWEEN :min_price AND :max_price
GROUP BY i.id
HAVING COUNT(DISTINCT it.tag_id) = :required_tag_count  -- must match ALL tags
ORDER BY matched_tags DESC, i.save_count DESC
LIMIT 24;
```

Indexes used: `idx_items_status_published`, `idx_item_tags_tag_id`, `idx_items_price`.

---

### QP-2: Full-Text Search

**"Search for 'leather journal' across title and description"**

```sql
SELECT i.id, i.title, i.price,
       ts_rank(i.search_tsv, query) AS rank
FROM items i,
     to_tsquery('english', 'leather & journal') AS query
WHERE i.status = 'active'
  AND i.search_tsv @@ query
ORDER BY rank DESC
LIMIT 24;
```

Index used: `idx_items_search_tsv` (GIN).

---

### QP-3: AI Semantic / Natural-Language Search

**"Find gifts for a minimalist who loves hiking"**

The application layer converts the query string to a vector embedding via OpenAI/Claude API, then queries:

```sql
SELECT i.id, i.title, i.price,
       1 - (i.embedding <=> :query_vector::vector) AS similarity
FROM items i
WHERE i.status = 'active'
  AND i.embedding IS NOT NULL
ORDER BY i.embedding <=> :query_vector::vector
LIMIT 24;
```

Index used: `idx_items_embedding_ivfflat` (IVFFlat approximate NN).

For higher recall, combine with full-text (hybrid search):

```sql
-- Hybrid: RRF (Reciprocal Rank Fusion) at application layer
-- Run both queries, merge ranked lists
```

---

### QP-4: User Wishlist Read

**"Get all items in a user's wishlist, ordered by sort_order"**

```sql
SELECT wi.id, wi.priority, wi.note, wi.is_purchased, wi.sort_order,
       i.id AS item_id, i.title, i.price, i.image_url, i.product_url
FROM wishlist_items wi
JOIN items i ON i.id = wi.item_id
WHERE wi.wishlist_id = :wishlist_id
ORDER BY wi.sort_order ASC, wi.added_at DESC;
```

Indexes used: `idx_wishlist_items_wishlist`.

---

### QP-5: Review Queue — Admin Fetch Next Batch

**"Get next 20 unassigned pending items, highest priority first"**

```sql
SELECT rq.id, rq.item_id, rq.source, rq.priority, rq.entered_queue_at,
       i.title, i.image_url, i.source_url
FROM review_queue rq
JOIN items i ON i.id = rq.item_id
WHERE rq.assigned_to IS NULL
ORDER BY rq.priority DESC, rq.entered_queue_at ASC
LIMIT 20
FOR UPDATE SKIP LOCKED;  -- safe concurrent claiming by multiple admin workers
```

Index used: `idx_review_queue_priority`.

---

### QP-6: Recommendation Engine — Collaborative Signals

**"Find items popular among users who share interests with user X"**

```sql
-- Step 1: get top tags for target user
SELECT tag_id FROM recommendation_signals
WHERE user_id = :user_id
ORDER BY score DESC
LIMIT 20;

-- Step 2: score candidate items by tag overlap with user's affinity
SELECT i.id, i.title, i.price,
       SUM(rs.score) AS affinity_score
FROM items i
JOIN item_tags it ON it.item_id = i.id
JOIN recommendation_signals rs ON rs.tag_id = it.tag_id
    AND rs.user_id = :user_id
WHERE i.status = 'active'
  AND i.id NOT IN (
      SELECT item_id FROM user_interactions
      WHERE user_id = :user_id
        AND interaction IN ('dismiss', 'purchase')
  )
GROUP BY i.id
ORDER BY affinity_score DESC
LIMIT 24;
```

---

### QP-7: Scraper Job Queue — Worker Fetch

**"Pick the next queued scraper job to execute (priority queue)"**

```sql
UPDATE scraper_jobs
SET status = 'running', started_at = NOW()
WHERE id = (
    SELECT id FROM scraper_jobs
    WHERE status = 'queued'
    ORDER BY priority ASC, queued_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
RETURNING *;
```

Index used: `idx_scraper_jobs_status_queued`.

---

### QP-8: Instagram Review Queue — Fetch Pending Posts

**"Get pending Instagram posts for admin review, newest first"**

```sql
SELECT id, instagram_media_id, instagram_account, permalink,
       media_url, caption, suggested_tags, confidence_score, fetched_at
FROM instagram_queue
WHERE status = 'pending'
ORDER BY fetched_at DESC
LIMIT 50;
```

Index used: `idx_instagram_queue_status`.

---

### QP-9: Trending Items — Time-Windowed Engagement

**"Get most-saved items in the last 7 days"**

```sql
SELECT i.id, i.title, i.price, i.image_url,
       COUNT(*) FILTER (WHERE ui.interaction = 'save') AS saves_7d,
       COUNT(*) FILTER (WHERE ui.interaction = 'click') AS clicks_7d
FROM user_interactions ui
JOIN items i ON i.id = ui.item_id
WHERE ui.created_at >= NOW() - INTERVAL '7 days'
  AND ui.interaction IN ('save', 'click')
  AND i.status = 'active'
GROUP BY i.id
ORDER BY saves_7d DESC, clicks_7d DESC
LIMIT 24;
```

Index used: `idx_interactions_created_at`, `idx_interactions_item`.

> For production scale, this query is pre-computed by a nightly/hourly Celery task and cached in Redis.

---

### QP-10: Ingestion Audit Log — Job Summary

**"Get the event log for a specific scraper job run"**

```sql
SELECT il.id, il.event, il.source, il.details, il.created_at,
       i.title AS item_title
FROM ingestion_log il
LEFT JOIN items i ON i.id = il.item_id
WHERE il.job_id = :job_id
ORDER BY il.created_at ASC;
```

Index used: `idx_ingestion_log_job`.

---

## 6. Data Access Patterns

The repository pattern is used to isolate database logic from business logic. Each major entity has a dedicated repository class.

### 6.1 Base Repository

```python
# app/db/repositories/base.py
from typing import TypeVar, Generic, Optional, List
from uuid import UUID
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")

class BaseRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model: type[ModelT]):
        self._session = session
        self._model = model

    async def get_by_id(self, id: UUID | int) -> Optional[ModelT]:
        return await self._session.get(self._model, id)

    async def save(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self._session.delete(entity)
        await self._session.flush()
```

---

### 6.2 ItemRepository

```python
# app/db/repositories/item_repository.py
from dataclasses import dataclass
from typing import Optional, List
from uuid import UUID
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from .base import BaseRepository
from app.db.models import Item, ItemTag, Tag

@dataclass
class ItemFilterParams:
    tag_ids: List[int]          # resolved from filter selections
    min_price: Optional[float]
    max_price: Optional[float]
    status: str = "active"
    limit: int = 24
    offset: int = 0

class ItemRepository(BaseRepository[Item]):

    async def filter_by_profile(self, params: ItemFilterParams) -> List[Item]:
        """QP-1: Profile-based gift discovery."""
        ...

    async def fulltext_search(self, query: str, limit: int = 24) -> List[Item]:
        """QP-2: Full-text search via tsvector."""
        ...

    async def semantic_search(
        self, embedding: list[float], limit: int = 24
    ) -> List[Item]:
        """QP-3: pgvector cosine similarity search."""
        ...

    async def get_by_content_hash(self, content_hash: str) -> Optional[Item]:
        """Deduplication check before insert."""
        stmt = sa.select(Item).where(Item.content_hash == content_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def bulk_upsert(self, items: List[dict]) -> dict:
        """Bulk insert with on-conflict update for scraper imports."""
        stmt = sa.dialects.postgresql.insert(Item.__table__).values(items)
        stmt = stmt.on_conflict_do_update(
            index_elements=["source_site_id", "source_external_id"],
            set_={"title": stmt.excluded.title, "price": stmt.excluded.price,
                  "updated_at": sa.func.now()}
        )
        result = await self._session.execute(stmt)
        return {"rows_affected": result.rowcount}

    async def update_status(
        self, item_id: UUID, status: str,
        reviewed_by: UUID, rejection_reason: str | None = None
    ) -> Optional[Item]:
        """Admin approve/reject."""
        stmt = (
            sa.update(Item)
            .where(Item.id == item_id)
            .values(status=status, reviewed_by=reviewed_by,
                    reviewed_at=sa.func.now(),
                    rejection_reason=rejection_reason,
                    published_at=sa.case(
                        (sa.literal(status) == "active", sa.func.now()),
                        else_=Item.published_at
                    ))
            .returning(Item)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_trending(self, days: int = 7, limit: int = 24) -> List[dict]:
        """QP-9: Trending items — should be served from Redis cache."""
        ...
```

---

### 6.3 WishlistRepository

```python
# app/db/repositories/wishlist_repository.py
from uuid import UUID
from typing import List, Optional
import sqlalchemy as sa
from .base import BaseRepository
from app.db.models import Wishlist, WishlistItem

class WishlistRepository(BaseRepository[Wishlist]):

    async def get_user_wishlists(self, user_id: UUID) -> List[Wishlist]:
        stmt = (
            sa.select(Wishlist)
            .where(Wishlist.user_id == user_id)
            .order_by(Wishlist.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_share_token(self, token: str) -> Optional[Wishlist]:
        stmt = sa.select(Wishlist).where(
            Wishlist.share_token == token,
            Wishlist.is_public == True
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_item(
        self, wishlist_id: UUID, item_id: UUID,
        note: str | None = None, priority: int = 0
    ) -> WishlistItem:
        wi = WishlistItem(
            wishlist_id=wishlist_id, item_id=item_id,
            note=note, priority=priority
        )
        return await self.save(wi)

    async def remove_item(self, wishlist_id: UUID, item_id: UUID) -> bool:
        stmt = (
            sa.delete(WishlistItem)
            .where(WishlistItem.wishlist_id == wishlist_id,
                   WishlistItem.item_id == item_id)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def get_items(self, wishlist_id: UUID) -> List[WishlistItem]:
        """QP-4: Wishlist items with item details."""
        ...
```

---

### 6.4 ScraperJobRepository

```python
# app/db/repositories/scraper_job_repository.py
from uuid import UUID
from typing import Optional
import sqlalchemy as sa
from .base import BaseRepository
from app.db.models import ScraperJob

class ScraperJobRepository(BaseRepository[ScraperJob]):

    async def claim_next_job(self) -> Optional[ScraperJob]:
        """QP-7: Atomically claim next queued job (SKIP LOCKED)."""
        stmt = (
            sa.update(ScraperJob)
            .where(ScraperJob.id == (
                sa.select(ScraperJob.id)
                .where(ScraperJob.status == "queued")
                .order_by(ScraperJob.priority.asc(), ScraperJob.queued_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
                .scalar_subquery()
            ))
            .values(status="running", started_at=sa.func.now())
            .returning(ScraperJob)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def complete_job(self, job_id: UUID, stats: dict) -> None:
        stmt = (
            sa.update(ScraperJob)
            .where(ScraperJob.id == job_id)
            .values(status="completed", completed_at=sa.func.now(), **stats)
        )
        await self._session.execute(stmt)

    async def fail_job(
        self, job_id: UUID, error_message: str, error_traceback: str
    ) -> None:
        stmt = (
            sa.update(ScraperJob)
            .where(ScraperJob.id == job_id)
            .values(status="failed", completed_at=sa.func.now(),
                    error_message=error_message,
                    error_traceback=error_traceback)
        )
        await self._session.execute(stmt)

    async def enqueue(
        self, site_id: int, schedule_id: int | None = None,
        triggered_by: UUID | None = None,
        start_url: str | None = None,
        priority: int = 5
    ) -> ScraperJob:
        job = ScraperJob(
            site_id=site_id, schedule_id=schedule_id,
            triggered_by=triggered_by, start_url=start_url,
            priority=priority
        )
        return await self.save(job)
```

---

### 6.5 InstagramQueueRepository

```python
# app/db/repositories/instagram_queue_repository.py
from typing import List, Optional
from uuid import UUID
import sqlalchemy as sa
from .base import BaseRepository
from app.db.models import InstagramQueue

class InstagramQueueRepository(BaseRepository[InstagramQueue]):

    async def upsert_post(self, post_data: dict) -> InstagramQueue:
        """Insert or ignore duplicate media ids."""
        stmt = (
            sa.dialects.postgresql.insert(InstagramQueue.__table__)
            .values(**post_data)
            .on_conflict_do_nothing(index_elements=["instagram_media_id"])
            .returning(InstagramQueue)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending(self, limit: int = 50) -> List[InstagramQueue]:
        """QP-8: Admin review queue."""
        stmt = (
            sa.select(InstagramQueue)
            .where(InstagramQueue.status == "pending")
            .order_by(InstagramQueue.fetched_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def approve(
        self, queue_id: int, item_id: UUID, reviewed_by: UUID
    ) -> None:
        stmt = (
            sa.update(InstagramQueue)
            .where(InstagramQueue.id == queue_id)
            .values(status="approved", item_id=item_id,
                    reviewed_by=reviewed_by, reviewed_at=sa.func.now())
        )
        await self._session.execute(stmt)

    async def reject(
        self, queue_id: int, reviewed_by: UUID, reason: str
    ) -> None:
        stmt = (
            sa.update(InstagramQueue)
            .where(InstagramQueue.id == queue_id)
            .values(status="rejected", reviewed_by=reviewed_by,
                    reviewed_at=sa.func.now(), rejection_reason=reason)
        )
        await self._session.execute(stmt)
```

---

### 6.6 RecommendationRepository

```python
# app/db/repositories/recommendation_repository.py
from uuid import UUID
from typing import List
import sqlalchemy as sa
from .base import BaseRepository
from app.db.models import RecommendationSignal, Item

class RecommendationRepository(BaseRepository[RecommendationSignal]):

    async def upsert_signal(
        self, user_id: UUID, tag_id: int, score_delta: float
    ) -> None:
        """Called by background worker after each interaction."""
        stmt = sa.dialects.postgresql.insert(RecommendationSignal.__table__).values(
            user_id=user_id, tag_id=tag_id,
            score=score_delta, interaction_count=1
        ).on_conflict_do_update(
            index_elements=["user_id", "tag_id"],
            set_={
                "score": RecommendationSignal.score + sa.excluded.score,
                "interaction_count": RecommendationSignal.interaction_count + 1,
                "last_updated_at": sa.func.now()
            }
        )
        await self._session.execute(stmt)

    async def get_recommended_items(
        self, user_id: UUID, limit: int = 24
    ) -> List[Item]:
        """QP-6: Score items by user's tag affinity."""
        ...

    async def log_interaction(
        self, user_id: UUID, item_id: UUID,
        interaction: str, session_id: str | None = None,
        metadata: dict | None = None
    ) -> None:
        from app.db.models import UserInteraction
        record = UserInteraction(
            user_id=user_id, item_id=item_id,
            interaction=interaction,
            session_id=session_id,
            metadata=metadata or {}
        )
        self._session.add(record)
        await self._session.flush()
```

---

### 6.7 TagRepository

```python
# app/db/repositories/tag_repository.py
from typing import List, Optional, Dict
import sqlalchemy as sa
from .base import BaseRepository
from app.db.models import Tag, TagType

class TagRepository(BaseRepository[Tag]):

    async def get_all_filterable(self) -> Dict[str, List[Tag]]:
        """Load entire taxonomy for filter UI — cached in Redis for ~1 hour."""
        stmt = (
            sa.select(Tag, TagType.name.label("type_name"))
            .join(TagType, TagType.id == Tag.tag_type_id)
            .where(Tag.is_active == True, TagType.is_filterable == True)
            .order_by(TagType.sort_order, Tag.sort_order)
        )
        result = await self._session.execute(stmt)
        taxonomy: Dict[str, List[Tag]] = {}
        for tag, type_name in result:
            taxonomy.setdefault(type_name, []).append(tag)
        return taxonomy

    async def get_by_slugs(
        self, type_name: str, slugs: List[str]
    ) -> List[Tag]:
        stmt = (
            sa.select(Tag)
            .join(TagType, TagType.id == Tag.tag_type_id)
            .where(TagType.name == type_name, Tag.slug.in_(slugs))
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_item_tags(self, item_id) -> List[Tag]:
        from app.db.models import ItemTag
        stmt = (
            sa.select(Tag)
            .join(ItemTag, ItemTag.tag_id == Tag.id)
            .where(ItemTag.item_id == item_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
```

---

### Unit of Work Pattern

All repositories are composed in a `UnitOfWork` that wraps a single `AsyncSession`, ensuring atomicity across repositories:

```python
# app/db/unit_of_work.py
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

class UnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    @asynccontextmanager
    async def transaction(self):
        async with self._session_factory() as session:
            async with session.begin():
                yield self._make_repos(session)

    def _make_repos(self, session: AsyncSession):
        from types import SimpleNamespace
        return SimpleNamespace(
            items=ItemRepository(session, Item),
            tags=TagRepository(session, Tag),
            wishlists=WishlistRepository(session, Wishlist),
            scraper_jobs=ScraperJobRepository(session, ScraperJob),
            instagram_queue=InstagramQueueRepository(session, InstagramQueue),
            recommendations=RecommendationRepository(session, RecommendationSignal),
        )
```

Usage in a FastAPI service:

```python
async def approve_item(item_id: UUID, admin_id: UUID, uow: UnitOfWork):
    async with uow.transaction() as repos:
        item = await repos.items.update_status(item_id, "active", admin_id)
        await repos.ingestion_log.append(
            event="item_approved", source=item.source,
            item_id=item_id, actor_user_id=admin_id
        )
        # review_queue row removed automatically by DB trigger
```

---

## Appendix: Schema Dependency Order

For clean migrations, create tables in this order to satisfy foreign key constraints:

```
1.  tag_types
2.  tags                    (→ tag_types, self-ref parent_tag_id)
3.  users
4.  scraper_sites
5.  items                   (→ scraper_sites, users[reviewed_by])
6.  item_tags               (→ items, tags)
7.  wishlists               (→ users)
8.  wishlist_items          (→ wishlists, items)
9.  user_interactions       (→ users, items)
10. cron_schedules          (→ users)
11. scraper_jobs            (→ scraper_sites, cron_schedules, users)
12. instagram_queue         (→ users, items)
13. ingestion_log           (→ scraper_jobs, items, instagram_queue, users)
14. review_queue            (→ items, users)
15. recommendation_signals  (→ users, tags)
```

Note: `items` has a forward reference to `users` (for `reviewed_by`). Handle this by adding the FK as a deferred constraint or in a separate `ALTER TABLE` migration step after both tables exist.
