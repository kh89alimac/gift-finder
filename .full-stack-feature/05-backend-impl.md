# Backend Implementation: Gift Finder App

## Files Created (86 Python files + Docker/config)

### Core (`app/core/`)
- `exceptions.py` — `GiftFinderError` hierarchy (NotFound, Conflict, Forbidden, InvalidToken, Validation, RateLimit, ExternalService)
- `logging.py` — structlog JSON config with request_id ContextVar
- `redis.py` — async Redis client with pool
- `security.py` — bcrypt password hashing, JWT access/refresh tokens with JTI rotation, Redis-backed token family revocation

### App (`app/`)
- `main.py` — FastAPI app factory, lifespan, CORS, structlog request middleware, exception handlers
- `middleware.py` — request logging middleware injecting request_id and duration_ms
- `dependencies.py` — `get_db`, `get_uow`, `get_current_user`, `get_current_user_optional`, `require_admin`

### Schemas (`app/schemas/`)
9 Pydantic V2 schema files: common (PaginatedResponse, cursor pagination, ErrorResponse), auth, items (ItemSummary, ItemDetail, RecipientProfile), search, wishlists, recommendations, taxonomy, review_queue, ingestion, cron

### Services (`app/services/`) — 11 services
- `auth_service.py` — register, login (bcrypt verify), issue JWT pair, refresh (token family rotation), logout
- `item_service.py` — list_items, get_item_detail (with top-5 similar via pgvector), update_item_status, record_interaction
- `search_service.py` — full_text_search (tsvector), vector_search (pgvector ANN), ai_natural_language_search (OpenAI function calling → hybrid)
- `recommendation_service.py` — get_recommendations (stale-check + dispatch), compute_for_user (collaborative + content-based), get_similar_items
- `wishlist_service.py` — CRUD + add/remove items + share token generation
- `scraper_orchestrator.py` — trigger_site, resolve_adapter, auto_categorize (OpenAI function calling), persist_scraped_batch, mark_job_complete/failed
- `instagram_ingestion_service.py` — fetch_and_queue, approve_queue_item, reject_queue_item
- `manual_ingestion_service.py` — create_item, update_item, upload_image (S3 + EXIF strip), import_csv (SAVEPOINTs per row)
- `review_queue_service.py` — list_queue, approve/reject, bulk_approve/reject
- `taxonomy_service.py` — taxonomy CRUD, merge_tags (UPDATE → DELETE)
- `cron_scheduler_service.py` — schedule CRUD + trigger/enable/disable

### API Routers (`app/api/v1/`) — all thin, call services only
- `auth.py`, `items.py`, `search.py`, `wishlists.py`, `recommendations.py`
- `admin/review_queue.py`, `admin/taxonomy.py`, `admin/cron.py`, `admin/ingestion.py`
- `rate_limit.py` — slowapi config (5/min register, 10/min login, 30/min scraper trigger, 10/min Instagram trigger)

### Workers (`app/workers/`)
- `celery_app.py` — Celery factory, Redis broker/backend, celery-redbeat for DB-backed beat
- `tasks/scrape.py` — `scrape_site_task`: runs adapter, deduplicates, auto-categorizes, persists in 50-item batches, updates Redis progress
- `tasks/embed.py` — `embed_item_task`: calls OpenAI embeddings API, stores vector
- `tasks/instagram.py` — `instagram_fetch_task`: fetches posts, respects rate limit headers
- `tasks/recommendations.py` — `compute_recommendations_task`: collaborative + content-based filtering

### Adapters (`app/adapters/`)
- `base.py` — `BaseScrapeAdapter` ABC, `ScrapeResult` dataclass
- `registry.py` — dynamic adapter resolution by class path
- `generic_html.py` — CSS-selector-driven adapter (httpx + BeautifulSoup4), config from scraper_sites.config JSONB
- `amazon.py` — stub (Amazon requires headless browser; logs warning)
- `etsy.py` — Etsy public search HTML adapter

### Integrations (`app/integrations/`)
- `openai_client.py` — `embed_texts(texts)` (batched, text-embedding-3-small), `extract_gift_filters(query)` (function calling)
- `instagram_client.py` — `get_user_media`, `get_hashtag_media` (httpx, paginated)
- `s3_client.py` — `upload_file` (EXIF stripped via Pillow), `generate_presigned_url`

### Infrastructure
- `backend/docker/Dockerfile` — multi-stage build for API server
- `backend/docker/Dockerfile.worker` — multi-stage build for Celery worker
- `docker-compose.yml` — api, worker, beat, flower, postgres (pgvector), redis

## Key design decisions

- **Token family rotation**: JTI tracked in Redis; replaying a revoked token burns the entire user session family
- **Cursor pagination**: opaque base64 over `(published_at, id)` — keyset, O(1) deep paging
- **Scrape pipeline**: async iterators, 50-item commits, Redis progress tracking
- **Image upload**: magic-byte MIME validation, EXIF stripping, 10MB cap before S3 PUT
- **CSV import**: SAVEPOINTs per row — bad rows don't poison the transaction
- **Tag-merge**: two-step UPDATE-then-DELETE for safe dedup handling
- **Exception handling**: all `GiftFinderError` subclasses → uniform `ErrorResponse` with request_id
