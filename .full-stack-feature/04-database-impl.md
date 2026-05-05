# Database Implementation: Gift Finder App

## Files Created (28 total)

### Core
- `backend/app/core/config.py` — pydantic-settings `Settings` with DATABASE_URL, REDIS_URL, OPENAI_API_KEY, S3_BUCKET, JWT_SECRET
- `backend/app/core/database.py` — async engine, `async_session_factory`, `get_db()` FastAPI dependency

### Models (SQLAlchemy 2.0 async, Mapped[T] syntax)
- `backend/app/models/enums.py` — ItemStatus, ItemSource, UserRole, InteractionType, JobStatus, InstagramQueueStatus
- `backend/app/models/base.py` — `Base` + `TimestampMixin` + naming-convention metadata
- `backend/app/models/taxonomy.py` — `TagType`, `Tag` (self-FK hierarchy, JSONB metadata)
- `backend/app/models/catalog.py` — `ScraperSite`, `Item` (Vector(1536), TSVECTOR, SHA-256 content_hash), `ItemTag`
- `backend/app/models/user.py` — `User`, `Wishlist`, `WishlistItem`, `UserInteraction`
- `backend/app/models/ingestion.py` — `CronSchedule`, `ScraperJob`, `InstagramQueue`, `IngestionLog`
- `backend/app/models/admin.py` — `ReviewQueue`, `RecommendationSignal`

### Repositories
- `backend/app/repositories/base.py` — `BaseRepository[T]` generic CRUD (get, list, create, update, delete)
- `backend/app/repositories/items.py` — `search_by_profile` (keyset cursor pagination + tag intersection), `fulltext_search` (websearch_to_tsquery), `vector_search` (cosine ANN), `get_by_content_hash`, `upsert_from_scrape` (ON CONFLICT DO UPDATE)
- `backend/app/repositories/wishlists.py` — `get_with_items`, `add_item`, `remove_item`, `mark_purchased`
- `backend/app/repositories/tags.py` — `get_by_type`, `get_filterable_taxonomy`
- `backend/app/repositories/scraper_jobs.py` — `claim_next_job` (SKIP LOCKED), retry helpers
- `backend/app/repositories/instagram.py` — `claim_pending` (SKIP LOCKED), approve/reject
- `backend/app/repositories/recommendations.py` — `upsert_signal`, `upsert_signals_bulk`, `top_tags_for_user`
- `backend/app/repositories/unit_of_work.py` — `UnitOfWork` async context manager

### Migrations (Alembic async)
- `backend/app/migrations/env.py` — async env using `async_engine_from_config`
- `backend/app/migrations/versions/001_initial_schema.py` — full initial migration

### Config
- `backend/alembic.ini`
- `backend/pyproject.toml`

## Migration 001 installs

1. Extensions: `pgcrypto`, `pg_trgm`, `vector`, `btree_gist`
2. 6 ENUM types
3. 15 tables in dependency order
4. `UNIQUE NULLS NOT DISTINCT` on `items(source_site_id, source_external_id)` for scraper dedup
5. Triggers: `updated_at` (7 tables), `search_tsv` update (weighted A/B/C)
6. Indexes: GIN (search_tsv), IVFFlat cosine (embedding, lists=100), GIN+trigram (title), partial indexes for active items / queued jobs / pending queue, composite indexes for interactions and recommendation signals
7. Seed: 6 tag_types (interest, occasion, recipient, price_band, category, style)

## Key design decisions

- `expire_on_commit=False` on session factory for async safety
- Keyset (cursor) pagination on `(published_at DESC, id DESC)` — O(1) deep paging
- `JSONB` columns named `tag_metadata`/`log_metadata` to avoid SQLAlchemy `metadata` collision
- `UnitOfWork` owns transactional boundary; repos only `flush()`, caller controls commits
- `SKIP LOCKED` in job claiming prevents concurrent worker conflicts
- `ON CONFLICT DO UPDATE` in upsert paths keeps writes single-round-trip and race-free
