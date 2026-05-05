# Database Schema

## Overview

The Gift Finder database uses PostgreSQL 16 with the following extensions:

| Extension | Purpose |
|-----------|---------|
| `pgcrypto` | `gen_random_uuid()` for primary keys |
| `pg_trgm` | Trigram GIN index on `items.title` for fast ILIKE / similarity search |
| `vector` | pgvector — 1536-dimension embeddings stored in `items.embedding` |
| `btree_gist` | Range-type index support (reserved for future use) |

The entire schema is created by two Alembic migrations. There are no manual `CREATE TABLE` scripts.

---

## Tables (15 total)

Tables are listed in foreign-key dependency order (the order migration 001 creates them).

| # | Table | Purpose |
|---|-------|---------|
| 1 | `tag_types` | Taxonomy dimensions: interest, occasion, recipient, price_band, category, style |
| 2 | `tags` | Individual tags within each type; self-referential `parent_tag_id` for hierarchy |
| 3 | `scraper_sites` | One row per retailer site; holds adapter class name and rate-limit config |
| 4 | `users` | User accounts; supports email/password and OAuth |
| 5 | `items` | Central catalog table — all products regardless of ingestion source |
| 6 | `item_tags` | Many-to-many join between items and tags |
| 7 | `wishlists` | User-created gift lists; `share_token` enables public sharing |
| 8 | `wishlist_items` | Items added to a wishlist with priority and notes |
| 9 | `user_interactions` | Per-user interaction events (view, click, save, etc.) for recommendations |
| 10 | `cron_schedules` | celery-redbeat schedule definitions managed by the admin panel |
| 11 | `scraper_jobs` | One row per scrape run; tracks status, counters, retries |
| 12 | `instagram_queue` | Ingested Instagram posts awaiting admin review |
| 13 | `ingestion_log` | Append-only event log for all ingestion activity |
| 14 | `review_queue` | Admin moderation queue; one entry per item pending review |
| 15 | `recommendation_signals` | Pre-aggregated user-tag affinity scores for recommendation ranking |

---

## Key table details

### `items`

The central catalog table. All three ingestion pipelines write to it.

```
id               UUID PK  (gen_random_uuid())
title            VARCHAR(500)
description      TEXT
price            NUMERIC(12,2)
currency         CHAR(3)       default 'USD'
image_url        TEXT
image_s3_key     TEXT
product_url      TEXT
brand            VARCHAR(200)
retailer         VARCHAR(200)
source           item_source   enum: scraper | instagram | manual | csv_import
source_site_id   INT FK → scraper_sites.id ON DELETE SET NULL
source_external_id TEXT
source_url       TEXT
status           item_status   enum: pending_review | active | rejected | archived
rejection_reason TEXT
reviewed_by      UUID FK → users.id ON DELETE SET NULL
reviewed_at      TIMESTAMPTZ
embedding        VECTOR(1536)  pgvector — OpenAI text-embedding-3-small
search_tsv       TSVECTOR      auto-maintained by trigger
content_hash     CHAR(64)      SHA-256 of normalized content for dedup
view_count       INT default 0
save_count       INT default 0
click_count      INT default 0
published_at     TIMESTAMPTZ
created_at       TIMESTAMPTZ
updated_at       TIMESTAMPTZ   auto-maintained by trigger
```

**Unique constraint**: `(source_site_id, source_external_id) NULLS NOT DISTINCT` — prevents duplicate items from the same site; `NULLS NOT DISTINCT` means two rows with a non-null `source_external_id` and a null `source_site_id` still collide.

### `recommendation_signals`

Composite primary key `(user_id, tag_id)`. Scores are recomputed from `user_interactions` by the Celery recommendations task.

```
user_id           UUID FK → users.id ON DELETE CASCADE
tag_id            INT  FK → tags.id  ON DELETE CASCADE
score             NUMERIC(8,4)   0–9999.9999
interaction_count INT
updated_at        TIMESTAMPTZ
```

---

## ENUM types

| Name | Values |
|------|--------|
| `item_status` | `pending_review`, `active`, `rejected`, `archived` |
| `item_source` | `scraper`, `instagram`, `manual`, `csv_import` |
| `user_role` | `user`, `admin` |
| `interaction_type` | `view`, `click`, `save`, `remove`, `share`, `purchase`, `dismiss` |
| `job_status` | `queued`, `running`, `completed`, `failed`, `cancelled` |
| `instagram_queue_status` | `pending`, `approved`, `rejected`, `skipped` |

---

## Triggers

| Trigger | Table(s) | Event | Action |
|---------|----------|-------|--------|
| `trg_<table>_set_updated_at` | scraper_sites, items, users, wishlists, scraper_jobs, instagram_queue, cron_schedules | BEFORE UPDATE | Sets `updated_at = NOW()` |
| `trg_items_search_tsv` | items | BEFORE INSERT OR UPDATE of title/brand/retailer/description | Rebuilds `search_tsv` with weighted tsvectors (title=A, brand/retailer=B, description=C) |

---

## Notable indexes

| Index | Type | Notes |
|-------|------|-------|
| `ix_items_status_published_at` | B-tree composite | Hot path for the discovery feed (`WHERE status='active' ORDER BY published_at DESC`) |
| `ix_items_active_published` | Partial B-tree | Covers `(published_at DESC, id)` where `status='active'` — used for cursor pagination |
| `ix_items_search_tsv` | GIN | Full-text search |
| `ix_items_title_trgm` | GIN (trgm) | ILIKE / trigram similarity on title |
| `ix_items_embedding_hnsw` | HNSW | Vector ANN search (migration 002); partial: `status='active' AND embedding IS NOT NULL` |
| `ix_recommendation_signals_user_score` | B-tree | Fast top-N tag lookup per user |
| `ix_scraper_jobs_queued_priority` | Partial B-tree | SKIP LOCKED claim query for Celery workers |
| `ix_instagram_queue_pending_score` | Partial B-tree | Sorts pending IG posts by confidence score |
| `ix_instagram_queue_hashtags` | GIN (array) | Hashtag-based lookups |

---

## Seed data

Migration 001 inserts the six canonical `tag_types` rows:

| name | sort_order | is_filterable |
|------|-----------|--------------|
| interest | 10 | true |
| occasion | 20 | true |
| recipient | 30 | true |
| price_band | 40 | true |
| category | 50 | true |
| style | 60 | true |

Individual tags (`tags` table) are inserted via the admin panel or the CSV import; none are seeded automatically.

---

## Migrations

### Migration 001 — `001_initial_schema`

Creates everything from scratch in a single transaction:

1. PostgreSQL extensions
2. ENUM types
3. Trigger functions (`trg_set_updated_at`, `trg_items_update_search_tsv`)
4. All 15 tables in dependency order
5. All indexes (including the initial IVFFlat vector index with 100 lists)
6. Triggers attached to each table
7. Seed `tag_types` rows

Rollback drops all tables, triggers, trigger functions, and ENUM types in reverse order. Extensions are intentionally not dropped on rollback (other schemas in the cluster may depend on them).

### Migration 002 — `002_hnsw_index`

Replaces the IVFFlat vector index with HNSW for better recall at scale.

**Important**: this migration uses `CREATE INDEX CONCURRENTLY` and `DROP INDEX CONCURRENTLY`. Alembic runs migrations inside a transaction by default, but `CONCURRENTLY` operations cannot run inside a transaction block. The migration file handles this correctly — however, if you need to run it manually you must do so outside a transaction:

```sql
-- Run outside a transaction (psql: \set AUTOCOMMIT on)
DROP INDEX CONCURRENTLY IF EXISTS ix_items_embedding_ivfflat;

CREATE INDEX CONCURRENTLY ix_items_embedding_hnsw
  ON items USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64)
  WHERE status = 'active' AND embedding IS NOT NULL;
```

HNSW parameters:
- `m = 16` — number of bidirectional links per node; higher improves recall at the cost of index size and build time
- `ef_construction = 64` — size of the dynamic candidate list during index construction; higher improves build-time recall

---

## Running migrations

```bash
# Apply all pending migrations
cd backend
alembic upgrade head

# Check current revision
alembic current

# Roll back one step
alembic downgrade -1

# Roll back to the initial schema (removes migration 002)
alembic downgrade 001_initial_schema

# Roll back everything
alembic downgrade base
```

Alembic configuration is in `backend/alembic.ini`. The migration environment reads `DATABASE_URL` from the environment.
