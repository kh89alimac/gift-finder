# Gift Finder — Complete Backend & Frontend Architecture

> Document version: 1.0 | Date: 2026-05-03
> Stack: FastAPI · PostgreSQL/pgvector · Celery/Redis · Next.js 14 App Router · TypeScript · Tailwind CSS · OpenAI · AWS S3

---

## Table of Contents

1. [Backend Architecture](#1-backend-architecture)
   - 1.1 [Project Structure](#11-project-structure)
   - 1.2 [API Design](#12-api-design)
   - 1.3 [Service Layer](#13-service-layer)
   - 1.4 [Background Workers](#14-background-workers)
   - 1.5 [Authentication & Authorization](#15-authentication--authorization)
   - 1.6 [Scraper Adapter Pattern](#16-scraper-adapter-pattern)
2. [Frontend Architecture](#2-frontend-architecture)
   - 2.1 [App Router Structure](#21-app-router-structure)
   - 2.2 [Component Hierarchy](#22-component-hierarchy)
   - 2.3 [State Management](#23-state-management)
   - 2.4 [API Integration](#24-api-integration)
   - 2.5 [Admin Panel UX](#25-admin-panel-ux)
3. [Cross-Cutting Concerns](#3-cross-cutting-concerns)
   - 3.1 [Error Handling](#31-error-handling)
   - 3.2 [Security](#32-security)
   - 3.3 [Observability](#33-observability)
   - 3.4 [Risk Assessment](#34-risk-assessment)

---

## 1. Backend Architecture

### 1.1 Project Structure

```
backend/
├── pyproject.toml                  # uv/pip dependencies + project metadata
├── alembic/                        # Database migrations
│   ├── env.py
│   └── versions/
├── app/
│   ├── main.py                     # FastAPI app factory, lifespan, middleware
│   ├── config.py                   # Pydantic Settings (env-driven)
│   ├── database.py                 # Async SQLAlchemy engine + session factory
│   ├── dependencies.py             # Shared FastAPI Depends: get_db, get_current_user, require_admin
│   │
│   ├── api/                        # HTTP layer — thin, no business logic
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── router.py           # Aggregates all v1 sub-routers
│   │   │   ├── auth.py
│   │   │   ├── items.py
│   │   │   ├── search.py
│   │   │   ├── wishlists.py
│   │   │   ├── recommendations.py
│   │   │   └── admin/
│   │   │       ├── router.py       # Admin sub-router (prefix /admin, require_admin dep)
│   │   │       ├── review_queue.py
│   │   │       ├── taxonomy.py
│   │   │       ├── cron.py
│   │   │       └── ingestion.py
│   │
│   ├── schemas/                    # Pydantic request/response models
│   │   ├── auth.py
│   │   ├── items.py
│   │   ├── search.py
│   │   ├── wishlists.py
│   │   ├── recommendations.py
│   │   ├── taxonomy.py
│   │   ├── review_queue.py
│   │   ├── ingestion.py
│   │   ├── cron.py
│   │   └── common.py               # PaginatedResponse, ErrorResponse, etc.
│   │
│   ├── models/                     # SQLAlchemy ORM models (mirror DB tables)
│   │   ├── base.py                 # DeclarativeBase + common mixins (id, timestamps)
│   │   ├── taxonomy.py             # TagType, Tag
│   │   ├── catalog.py              # Item, ItemTag
│   │   ├── users.py                # User, Wishlist, WishlistItem, UserInteraction
│   │   └── ingestion.py            # ScraperSite, ScraperJob, CronSchedule,
│   │                               #   InstagramQueue, IngestionLog, ReviewQueue
│   │
│   ├── repositories/               # Data-access layer — all SQL lives here
│   │   ├── base.py                 # Generic BaseRepository[T]
│   │   ├── unit_of_work.py         # UnitOfWork wrapping AsyncSession
│   │   ├── item_repository.py
│   │   ├── wishlist_repository.py
│   │   ├── scraper_job_repository.py
│   │   ├── instagram_queue_repository.py
│   │   ├── tag_repository.py
│   │   └── recommendation_repository.py
│   │
│   ├── services/                   # Business logic, orchestration
│   │   ├── item_service.py
│   │   ├── search_service.py
│   │   ├── recommendation_service.py
│   │   ├── wishlist_service.py
│   │   ├── scraper_orchestrator.py
│   │   ├── instagram_ingestion_service.py
│   │   ├── manual_ingestion_service.py
│   │   ├── review_queue_service.py
│   │   ├── taxonomy_service.py
│   │   └── cron_scheduler_service.py
│   │
│   ├── workers/                    # Celery application + tasks
│   │   ├── celery_app.py           # Celery() factory, beat_schedule
│   │   ├── tasks/
│   │   │   ├── scrape.py           # scrape_site_task
│   │   │   ├── embed.py            # embed_item_task
│   │   │   ├── instagram.py        # instagram_fetch_task
│   │   │   └── recommendations.py  # compute_recommendations_task
│   │   └── beat_schedule.py        # Static + DB-backed beat entries
│   │
│   ├── adapters/                   # Scraper adapter plugin system
│   │   ├── base.py                 # BaseScrapeAdapter ABC
│   │   ├── registry.py             # {site_key: AdapterClass} dict
│   │   ├── amazon.py
│   │   ├── etsy.py
│   │   ├── uncommongoods.py
│   │   └── generic_html.py         # Fallback CSS-selector-driven adapter
│   │
│   ├── integrations/               # Third-party SDK wrappers
│   │   ├── openai_client.py        # Embedding + function-calling helpers
│   │   ├── instagram_client.py     # Meta Graph API wrapper
│   │   └── s3_client.py            # Boto3 async wrapper
│   │
│   └── core/                       # Pure utilities, no I/O
│       ├── security.py             # JWT encode/decode, password hashing
│       ├── hashing.py              # content_hash for dedup
│       ├── exceptions.py           # Domain exception hierarchy
│       ├── logging.py              # structlog configuration
│       └── pagination.py           # Cursor/offset pagination helpers
│
├── tests/
│   ├── conftest.py                 # pytest fixtures: test DB, mock clients
│   ├── unit/
│   └── integration/
└── docker/
    ├── Dockerfile
    └── Dockerfile.worker
```

**Key design decisions:**
- `api/` routers are import-only facades — they call services, never repositories directly.
- `repositories/` own all SQL. Services own all business rules. This separation makes both unit-testable in isolation.
- `workers/` import from `services/` (not `api/`), keeping task logic DRY.
- Adapters are discovered from `registry.py`; adding a new site means dropping one file and one registry entry.

---

### 1.2 API Design

All routes are prefixed `/api/v1`. JSON bodies use camelCase on the wire (Pydantic `alias_generator=to_camel`). Timestamps are ISO-8601 UTC strings. Pagination uses `?page=1&page_size=20` (offset) except for the feed which uses cursor.

#### Auth — `/api/v1/auth`

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `POST` | `/register` | — | `{ email, password, full_name }` | `{ user: UserOut, access_token, refresh_token }` |
| `POST` | `/login` | — | `{ email, password }` (form or JSON) | `{ access_token, refresh_token, token_type: "bearer" }` |
| `POST` | `/refresh` | refresh JWT (cookie or body) | `{ refresh_token }` | `{ access_token, refresh_token }` |
| `POST` | `/logout` | Bearer | — | `204 No Content` |
| `GET` | `/me` | Bearer | — | `UserOut` |

```python
# schemas/auth.py
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: Literal["user", "admin"]
    created_at: datetime
```

---

#### Items / Discovery — `/api/v1/items`

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| `GET` | `/` | Optional Bearer | Query filters (see below) | `PaginatedResponse[ItemSummary]` |
| `GET` | `/{item_id}` | Optional Bearer | — | `ItemDetail` |
| `GET` | `/search` | Optional Bearer | `?q=&mode=text\|vector` + filters | `PaginatedResponse[ItemSummary]` |
| `POST` | `/search/ai` | Optional Bearer | `{ query: str, profile: RecipientProfile }` | `{ items: ItemSummary[], interpretation: str }` |
| `GET` | `/categories` | — | — | `CategoryTree[]` |
| `GET` | `/occasions` | — | — | `Tag[]` |

**Discovery filter query parameters:**
```
age_min, age_max          integer
relationship              string (enum: parent, sibling, friend, partner, colleague, child)
occasion                  string[] (tag slugs, OR-joined)
interests                 string[] (tag slugs, OR-joined)
budget_min, budget_max    decimal
source                    string[] (scraper, instagram, manual)
sort                      enum: relevance | price_asc | price_desc | newest | popular
cursor                    string (opaque, for cursor pagination)
page_size                 integer (1–100, default 20)
```

```python
# schemas/items.py
class ItemSummary(BaseModel):
    id: UUID
    title: str
    price: Decimal
    price_currency: str
    image_url: str | None
    source: ItemSource
    tags: list[TagSlim]
    affiliate_url: str | None
    relevance_score: float | None      # present on search results

class ItemDetail(ItemSummary):
    description: str | None
    brand: str | None
    retailer: str | None
    images: list[str]
    occasion_tags: list[TagSlim]
    interest_tags: list[TagSlim]
    age_min: int | None
    age_max: int | None
    similar_items: list[ItemSummary]   # top-5 from pgvector ANN

class RecipientProfile(BaseModel):
    age: int | None = None
    relationship: str | None = None
    interests: list[str] = []
    occasion: str | None = None
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
```

---

#### Wishlists — `/api/v1/wishlists`

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/` | Bearer | — | `list[WishlistSummary]` |
| `POST` | `/` | Bearer | `{ name, is_public, description? }` | `WishlistDetail` |
| `GET` | `/{wishlist_id}` | Optional Bearer (public lists) | — | `WishlistDetail` |
| `PUT` | `/{wishlist_id}` | Bearer (owner) | `{ name?, is_public?, description? }` | `WishlistDetail` |
| `DELETE` | `/{wishlist_id}` | Bearer (owner) | — | `204` |
| `POST` | `/{wishlist_id}/items` | Bearer (owner) | `{ item_id, note? }` | `WishlistItemOut` |
| `DELETE` | `/{wishlist_id}/items/{item_id}` | Bearer (owner) | — | `204` |
| `GET` | `/{wishlist_id}/share` | Bearer (owner) | — | `{ share_url: str, share_token: str }` |

```python
class WishlistDetail(BaseModel):
    id: UUID
    name: str
    is_public: bool
    share_token: str | None
    item_count: int
    items: list[WishlistItemOut]
    created_at: datetime
```

---

#### Recommendations — `/api/v1/recommendations`

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| `GET` | `/` | Bearer | `?profile=<json>&page_size=20` | `PaginatedResponse[ItemSummary]` |
| `POST` | `/refresh` | Bearer | — | `{ task_id: str }` (202 Accepted) |
| `GET` | `/similar/{item_id}` | Optional Bearer | `?page_size=5` | `list[ItemSummary]` |

---

#### Admin: Review Queue — `/api/v1/admin/queue`

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| `GET` | `/` | Admin | `?status=pending\|approved\|rejected&source=&page=&page_size=` | `PaginatedResponse[ReviewQueueItem]` |
| `GET` | `/{queue_id}` | Admin | — | `ReviewQueueItem` |
| `POST` | `/{queue_id}/approve` | Admin | `{ item_patch?: Partial<ItemIn> }` | `ReviewQueueItem` |
| `POST` | `/{queue_id}/reject` | Admin | `{ reason: str }` | `ReviewQueueItem` |
| `POST` | `/bulk-approve` | Admin | `{ queue_ids: UUID[] }` | `BulkActionResult` |
| `POST` | `/bulk-reject` | Admin | `{ queue_ids: UUID[], reason: str }` | `BulkActionResult` |

---

#### Admin: Taxonomy — `/api/v1/admin/taxonomy`

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/tag-types` | Admin | — | `list[TagTypeOut]` |
| `POST` | `/tag-types` | Admin | `{ name, slug, description? }` | `TagTypeOut` |
| `PUT` | `/tag-types/{id}` | Admin | `{ name?, slug?, description? }` | `TagTypeOut` |
| `DELETE` | `/tag-types/{id}` | Admin | — | `204` |
| `GET` | `/tags` | Admin | `?tag_type_id=&search=&page=` | `PaginatedResponse[TagOut]` |
| `POST` | `/tags` | Admin | `{ name, slug, tag_type_id, metadata? }` | `TagOut` |
| `PUT` | `/tags/{id}` | Admin | `{ name?, slug?, metadata? }` | `TagOut` |
| `DELETE` | `/tags/{id}` | Admin | — | `204` |
| `POST` | `/tags/merge` | Admin | `{ source_id: UUID, target_id: UUID }` | `{ migrated_items: int }` |

---

#### Admin: Cron Schedules — `/api/v1/admin/cron`

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| `GET` | `/` | Admin | — | `list[CronScheduleOut]` |
| `POST` | `/` | Admin | `CronScheduleIn` | `CronScheduleOut` |
| `PUT` | `/{id}` | Admin | `CronScheduleIn` | `CronScheduleOut` |
| `DELETE` | `/{id}` | Admin | — | `204` |
| `POST` | `/{id}/trigger` | Admin | — | `{ job_id: UUID }` (202 Accepted) |
| `POST` | `/{id}/enable` | Admin | — | `CronScheduleOut` |
| `POST` | `/{id}/disable` | Admin | — | `CronScheduleOut` |

```python
class CronScheduleIn(BaseModel):
    name: str
    site_id: UUID
    cron_expression: str   # e.g. "0 2 * * *"
    enabled: bool = True
    config_override: dict = {}

class CronScheduleOut(CronScheduleIn):
    id: UUID
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_job_status: str | None
```

---

#### Admin: Ingestion — `/api/v1/admin/ingestion`

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| `POST` | `/scraper/trigger` | Admin | `{ site_id: UUID, priority?: int }` | `{ job_id: UUID }` (202) |
| `GET` | `/scraper/jobs` | Admin | `?status=&site_id=&page=` | `PaginatedResponse[ScraperJobOut]` |
| `GET` | `/scraper/jobs/{job_id}` | Admin | — | `ScraperJobOut` |
| `POST` | `/instagram/trigger` | Admin | `{ target: str, target_type: "account"\|"hashtag" }` | `{ task_id: str }` (202) |
| `GET` | `/instagram/queue` | Admin | `?status=&page=` | `PaginatedResponse[InstagramQueueItem]` |
| `POST` | `/items` | Admin | `ItemManualIn` | `ItemDetail` (201) |
| `PUT` | `/items/{item_id}` | Admin | `Partial<ItemManualIn>` | `ItemDetail` |
| `POST` | `/items/csv` | Admin | multipart `file: UploadFile` | `{ accepted: int, rejected: int, errors: CsvRowError[] }` |
| `POST` | `/items/{item_id}/images` | Admin | multipart `image: UploadFile` | `{ image_url: str }` |

```python
class ItemManualIn(BaseModel):
    title: str
    description: str | None = None
    price: Decimal
    price_currency: str = "USD"
    brand: str | None = None
    retailer: str | None = None
    affiliate_url: HttpUrl | None = None
    tag_ids: list[UUID] = []
    age_min: int | None = None
    age_max: int | None = None
    status: Literal["draft", "active"] = "draft"
```

---

### 1.3 Service Layer

Each service is a class injected via FastAPI `Depends` (or constructed in Celery tasks with a standalone async session). Services accept a `UnitOfWork` instance; they do not manage transactions themselves.

---

#### `ItemService`
```
Responsibilities:
  - list_items(filters, pagination) → calls ItemRepository with compiled WHERE clauses
  - get_item_detail(item_id) → item + tags + top-5 similar via pgvector cosine query
  - update_item_status(item_id, status) → draft → active lifecycle
  - record_interaction(user_id, item_id, type) → feeds UserInteraction table
  - build_similar_items_query(embedding) → pgvector ANN with ivfflat index

Dependencies: ItemRepository, TagRepository
```

#### `SearchService`
```
Responsibilities:
  - full_text_search(query, filters) → PostgreSQL tsvector/tsquery on search_tsv column
  - vector_search(query_text, filters) → embed query via OpenAI, then pgvector <=> operator
  - ai_natural_language_search(query, profile) → parse intent via OpenAI function calling
      → extract structured filters from response
      → hybrid: combine vector ANN results with hard filter WHERE clause
      → return items + human-readable interpretation string

Dependencies: ItemRepository, OpenAIClient
```

#### `RecommendationService`
```
Responsibilities:
  - get_recommendations(user_id, profile) → read pre-computed recommendation_signals
      → if stale (>1hr) dispatch compute_recommendations_task, serve cached result
  - compute_for_user(user_id) → collaborative filter via interaction history
      + content-based via mean embedding of wishlisted/viewed items
      → pgvector ANN against items.embedding
      → write back to recommendation_signals
  - get_similar_items(item_id, n) → direct pgvector query, no user context needed

Dependencies: RecommendationRepository, ItemRepository, UserInteractionRepository
```

#### `WishlistService`
```
Responsibilities:
  - create/update/delete wishlist, enforce per-user limit (configurable, default 10)
  - add/remove item with optimistic conflict handling (UNIQUE constraint)
  - generate_share_token() → URL-safe random token stored on wishlist row
  - get_by_share_token(token) → public access path, no auth required

Dependencies: WishlistRepository
```

#### `ScraperOrchestrator`
```
Responsibilities:
  - trigger_site(site_id, priority) → create ScraperJob row, enqueue scrape_site_task
  - resolve_adapter(site_key) → look up registry.py, instantiate adapter
  - dedup_item(content_hash) → query items table for existing hash, return bool
  - auto_categorize(raw_item) → call OpenAI function calling with item text
      → returns { tag_slugs: str[], age_min: int, age_max: int }
  - persist_scraped_batch(items, job_id) → bulk upsert, update job progress
  - mark_job_complete/failed(job_id, stats) → update scraper_jobs row

Dependencies: ScraperJobRepository, ItemRepository, TagRepository, OpenAIClient, registry
```

#### `InstagramIngestionService`
```
Responsibilities:
  - fetch_account_media(account_id) → paginated Graph API, write to instagram_queue
  - fetch_hashtag_media(hashtag_id) → paginated Graph API, write to instagram_queue
  - process_queue_item(queue_id) → extract product data from caption + media
      → create Item in draft/pending_review state
      → enqueue embed_item_task

Dependencies: InstagramQueueRepository, InstagramClient, ItemRepository
```

#### `ManualIngestionService`
```
Responsibilities:
  - create_item(item_in) → validate, persist, enqueue embed_item_task
  - update_item(item_id, patch) → partial update, re-embed if title/description changed
  - upload_image(item_id, file) → validate MIME (image/jpeg, image/png, image/webp),
      resize to max 1200px, upload to S3, append URL to items.images
  - import_csv(file) → stream-parse, validate each row via Pydantic, bulk insert,
      return accepted/rejected counts + per-row errors

Dependencies: ItemRepository, S3Client, celery tasks
```

#### `ReviewQueueService`
```
Responsibilities:
  - list_queue(filters) → paginated queue with joined item data
  - approve(queue_id, item_patch) → apply patch to item, set status=active,
      update queue row reviewed_at + reviewer_id
  - reject(queue_id, reason) → set item status=rejected, record reason
  - bulk_approve / bulk_reject → iterate with per-item error isolation

Dependencies: ReviewQueueRepository, ItemRepository, UnitOfWork (transaction wraps both)
```

#### `TaxonomyService`
```
Responsibilities:
  - CRUD for TagType and Tag with slug uniqueness enforcement
  - merge_tags(source_id, target_id) → migrate all item_tags rows, delete source
  - get_tag_tree() → nested dict grouped by tag_type for UI category browser
  - suggest_tags(text) → fuzzy match against tag names (pg_trgm similarity)

Dependencies: TagRepository
```

#### `CronSchedulerService`
```
Responsibilities:
  - list_schedules() → all CronSchedule rows
  - create/update/delete schedule → persist to DB; also upsert Celery beat entry
      at runtime via app.add_periodic_task() (redbeat or DB scheduler)
  - trigger_now(schedule_id) → immediately enqueue scrape_site_task bypassing beat
  - enable/disable(schedule_id) → set enabled flag; beat reloads on next tick

Dependencies: CronScheduleRepository, ScraperOrchestrator, celery_app
Note: Uses celery-redbeat (Redis-backed beat store) so schedule changes propagate
      to the beat process without restart.
```

---

### 1.4 Background Workers

#### Celery Application Setup

```python
# workers/celery_app.py
from celery import Celery
from app.config import settings

celery_app = Celery(
    "giftfinder",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.tasks.scrape",
        "app.workers.tasks.embed",
        "app.workers.tasks.instagram",
        "app.workers.tasks.recommendations",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,             # re-queue on worker crash
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,    # fair dispatch for long scrape tasks
    task_routes={
        "app.workers.tasks.scrape.*":     {"queue": "scraping"},
        "app.workers.tasks.embed.*":      {"queue": "embeddings"},
        "app.workers.tasks.instagram.*":  {"queue": "ingestion"},
        "app.workers.tasks.recommendations.*": {"queue": "recommendations"},
    },
    beat_scheduler="redbeat.RedBeatScheduler",  # celery-redbeat for dynamic schedules
    redbeat_redis_url=settings.REDIS_URL,
)
```

---

#### `scrape_site_task(site_id, job_id)`

```python
# workers/tasks/scrape.py
@celery_app.task(
    bind=True,
    name="app.workers.tasks.scrape.scrape_site_task",
    max_retries=3,
    default_retry_delay=300,         # 5 min back-off
    soft_time_limit=1800,            # 30 min
    time_limit=2100,
    autoretry_for=(RequestException, TimeoutError),
)
def scrape_site_task(self, site_id: str, job_id: str) -> dict:
    """
    1. Load ScraperSite config from DB (adapter_key, base_url, selectors, auth_config)
    2. Resolve adapter: adapter = registry[site.adapter_key](site.config)
    3. Update job status → "running"
    4. Call adapter.scrape() → yields ScrapeResult(title, price, url, images, raw_text)
    5. For each result:
       a. content_hash = sha256(url + title + price)
       b. Skip if hash exists in items table (dedup)
       c. Call openai_client.categorize(raw_text) → {tag_slugs, age_min, age_max}
       d. Persist Item(status="pending_review"), ItemTag rows
       e. Enqueue embed_item_task.delay(item_id)
       f. Append to IngestionLog
    6. Update job: status="completed", items_found, items_new, items_skipped, completed_at
    7. Return stats dict
    """
```

**Progress tracking:** The task writes incremental progress (e.g., `{"processed": 47, "total": 200}`) to Redis using `self.update_state(state="PROGRESS", meta=...)`. The admin API `/scraper/jobs/{job_id}` polls this via Celery result backend.

---

#### `embed_item_task(item_id)`

```python
@celery_app.task(
    name="app.workers.tasks.embed.embed_item_task",
    max_retries=5,
    default_retry_delay=60,
    autoretry_for=(openai.RateLimitError, openai.APITimeoutError),
)
def embed_item_task(item_id: str) -> None:
    """
    1. Load item title + description from DB
    2. Concatenate: "{title}. {description}"
    3. Call openai.embeddings.create(model="text-embedding-3-small", input=text)
    4. Store 1536-dim vector in items.embedding via pgvector:
       UPDATE items SET embedding = %s WHERE id = %s
    5. Log cost estimate to ingestion_log (token count × per-token price)
    """
```

**Batching optimization:** A companion `embed_items_batch_task(item_ids: list[str])` groups up to 100 items per OpenAI API call (the Embeddings API accepts input arrays) to reduce cost and latency. Single-item task delegates to batch task when queue depth > 50.

---

#### `instagram_fetch_task(target, target_type)`

```python
@celery_app.task(
    name="app.workers.tasks.instagram.instagram_fetch_task",
    max_retries=2,
    default_retry_delay=900,         # 15 min — respect rate limit windows
    rate_limit="10/m",               # Celery-level rate limiting
)
def instagram_fetch_task(target: str, target_type: str) -> dict:
    """
    target_type = "account" | "hashtag"
    1. Authenticate via Meta Graph API (long-lived page token from config)
    2. Fetch paginated media (fields: id, caption, media_url, permalink, timestamp)
       — account: GET /{ig_user_id}/media
       — hashtag: GET /{hashtag_id}/recent_media
    3. For each post:
       a. Skip if permalink already in instagram_queue (dedup by ig_media_id)
       b. Insert into instagram_queue (status="pending", raw_data=full JSON)
    4. Return { fetched, inserted, skipped }
    """
```

**Rate-limit handling:** Checks `X-App-Usage` and `X-Business-Use-Case-Usage` response headers. If `call_count > 80%`, backs off exponentially and records warning in `ingestion_log`.

---

#### `compute_recommendations_task(user_id)`

```python
@celery_app.task(
    name="app.workers.tasks.recommendations.compute_recommendations_task",
    soft_time_limit=120,
)
def compute_recommendations_task(user_id: str) -> None:
    """
    1. Load user interaction history (viewed, wishlisted, purchased — last 90 days)
    2. Fetch embeddings for all interacted items
    3. Compute mean embedding weighted by interaction type:
       wishlist × 3.0, purchase × 5.0, view × 1.0
    4. pgvector ANN: SELECT id FROM items ORDER BY embedding <=> %mean_vec LIMIT 100
    5. Re-rank by:
       a. Price range affinity (from past interactions)
       b. Popularity score
       c. Recency (prefer items added in last 30 days)
    6. Write top-50 item_ids + scores to recommendation_signals table
    7. Set computed_at = NOW()
    """
```

---

#### Beat Schedule (Static + Dynamic)

```python
# workers/beat_schedule.py  — static entries; per-site schedules live in DB via redbeat

STATIC_BEAT_SCHEDULE = {
    # Refresh recommendations for active users every hour
    "hourly-recommendation-refresh": {
        "task": "app.workers.tasks.recommendations.refresh_active_users_task",
        "schedule": crontab(minute=0),
    },
    # Prune completed scraper jobs older than 7 days
    "daily-job-cleanup": {
        "task": "app.workers.tasks.scrape.cleanup_old_jobs_task",
        "schedule": crontab(hour=3, minute=0),
    },
    # Re-embed items whose embedding is NULL (catch failures)
    "retry-failed-embeddings": {
        "task": "app.workers.tasks.embed.retry_null_embeddings_task",
        "schedule": crontab(minute=30),
    },
}
```

Dynamic per-site schedules are stored in `cron_schedules` table and managed by `CronSchedulerService` which calls `redbeat.RedBeatSchedulerEntry` to add/remove entries without restarting the beat process.

---

### 1.5 Authentication & Authorization

#### JWT Strategy

- **Access token**: HS256, 15-minute expiry. Payload: `{ sub: user_id, role, jti, exp }`.
- **Refresh token**: HS256, 7-day expiry. Stored in `HttpOnly; Secure; SameSite=Strict` cookie AND returned in body (client chooses). Refresh token `jti` stored in Redis for revocation.
- **Token family rotation**: Each refresh issues a new refresh token and invalidates the old `jti`. Reuse of an already-rotated token triggers full session revocation (compromise detection).

#### Dependency Injection Pattern

```python
# dependencies.py
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    payload = decode_access_token(token)   # raises 401 on invalid/expired
    user = await UserRepository(db).get_by_id(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user

async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user

# Usage in router
@router.get("/admin/queue")
async def list_queue(
    admin: Annotated[User, Depends(require_admin)],
    service: Annotated[ReviewQueueService, Depends(get_review_queue_service)],
):
    ...
```

#### Password Security
- Hashing: `bcrypt` via `passlib[bcrypt]`, `rounds=12`.
- Rate limiting on `/auth/login`: 5 attempts per 15 min per IP via `slowapi` (Redis-backed).

---

### 1.6 Scraper Adapter Pattern

#### Abstract Base Class

```python
# adapters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import AsyncIterator

@dataclass
class ScrapeResult:
    title: str
    price: Decimal
    currency: str
    source_url: str          # canonical URL for dedup
    affiliate_url: str | None
    images: list[str]
    description: str | None
    brand: str | None
    raw_text: str            # concatenated text for OpenAI categorization
    extra: dict = field(default_factory=dict)

class BaseScrapeAdapter(ABC):
    """
    Contract every site adapter must implement.
    Adapters are stateless; all config is passed via __init__.
    """
    def __init__(self, site_config: dict) -> None:
        self.config = site_config

    @abstractmethod
    async def scrape(self) -> AsyncIterator[ScrapeResult]:
        """
        Yields ScrapeResult items one at a time (async generator).
        Must handle pagination internally.
        Must respect robots.txt and rate-limit delays.
        Raises AdapterError on unrecoverable failure.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Quick GET to site root; returns False if unreachable or structure changed."""
        ...
```

#### Concrete Adapter Example (Etsy)

```python
# adapters/etsy.py
class EtsyAdapter(BaseScrapeAdapter):
    BASE_URL = "https://openapi.etsy.com/v3"

    async def scrape(self) -> AsyncIterator[ScrapeResult]:
        # Uses Etsy Open API v3 — no HTML scraping needed
        async with httpx.AsyncClient() as client:
            offset, limit = 0, 100
            while True:
                r = await client.get(
                    f"{self.BASE_URL}/application/listings/active",
                    params={
                        "keywords": self.config["keywords"],
                        "limit": limit,
                        "offset": offset,
                        "includes": ["Images", "Shop"],
                    },
                    headers={"x-api-key": self.config["api_key"]},
                )
                r.raise_for_status()
                data = r.json()
                for listing in data["results"]:
                    yield ScrapeResult(
                        title=listing["title"],
                        price=Decimal(str(listing["price"]["amount"] / listing["price"]["divisor"])),
                        currency=listing["price"]["currency_code"],
                        source_url=listing["url"],
                        affiliate_url=None,
                        images=[i["url_fullxfull"] for i in listing.get("images", [])[:5]],
                        description=listing.get("description"),
                        brand=listing.get("shop", {}).get("shop_name"),
                        raw_text=f"{listing['title']} {listing.get('description', '')}",
                    )
                if len(data["results"]) < limit:
                    break
                offset += limit
                await asyncio.sleep(0.1)   # polite delay
```

#### Adapter Registry

```python
# adapters/registry.py
from app.adapters.amazon import AmazonAdapter
from app.adapters.etsy import EtsyAdapter
from app.adapters.uncommongoods import UncommonGoodsAdapter
from app.adapters.generic_html import GenericHtmlAdapter

ADAPTER_REGISTRY: dict[str, type[BaseScrapeAdapter]] = {
    "amazon":         AmazonAdapter,
    "etsy":           EtsyAdapter,
    "uncommongoods":  UncommonGoodsAdapter,
    "generic_html":   GenericHtmlAdapter,   # fallback: CSS selectors from site config
}

def get_adapter(adapter_key: str, config: dict) -> BaseScrapeAdapter:
    cls = ADAPTER_REGISTRY.get(adapter_key)
    if cls is None:
        raise ValueError(f"Unknown adapter: {adapter_key}")
    return cls(config)
```

#### Deduplication Strategy

```python
# core/hashing.py
import hashlib

def compute_content_hash(source_url: str, title: str, price: str) -> str:
    """
    Deterministic fingerprint. Normalized: lowercase title, rounded price.
    Same product at same price from same URL → same hash → skip insert.
    Price change on same URL → different hash → upsert with new price.
    """
    normalized = f"{source_url.lower()}|{title.lower().strip()}|{price}"
    return hashlib.sha256(normalized.encode()).hexdigest()
```

Dedup query uses `INSERT INTO items (...) ON CONFLICT (content_hash) DO UPDATE SET price=EXCLUDED.price, updated_at=NOW()` — so price updates are captured while true duplicates are skipped.

#### Auto-Categorization via OpenAI Function Calling

```python
# integrations/openai_client.py
CATEGORIZE_TOOLS = [{
    "type": "function",
    "function": {
        "name": "categorize_gift",
        "description": "Extract gift metadata from product text",
        "parameters": {
            "type": "object",
            "properties": {
                "tag_slugs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Relevant tag slugs from the provided taxonomy list",
                },
                "age_min": {"type": "integer", "description": "Minimum suitable recipient age"},
                "age_max": {"type": "integer", "description": "Maximum suitable recipient age"},
                "occasions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Occasion slugs (birthday, wedding, christmas, etc.)",
                },
            },
            "required": ["tag_slugs"],
        },
    },
}]

async def categorize_item(raw_text: str, available_tags: list[str]) -> CategorizeResult:
    system = (
        "You are a gift taxonomy assistant. Given product text, "
        "call categorize_gift with relevant tags from this list only: "
        + ", ".join(available_tags)
    )
    response = await openai_async_client.chat.completions.create(
        model="gpt-4o-mini",           # cost-efficient for bulk categorization
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": raw_text[:2000]},  # truncate to save tokens
        ],
        tools=CATEGORIZE_TOOLS,
        tool_choice={"type": "function", "function": {"name": "categorize_gift"}},
        temperature=0,
    )
    args = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
    return CategorizeResult(**args)
```

---

## 2. Frontend Architecture

### 2.1 App Router Structure

```
frontend/
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── openapi-ts.config.ts            # @hey-api/openapi-ts code-gen config
│
├── src/
│   ├── app/                        # Next.js App Router root
│   │   ├── layout.tsx              # Root layout: fonts, ThemeProvider, QueryProvider, Toaster
│   │   ├── page.tsx                # / → Home landing (Server Component)
│   │   ├── not-found.tsx
│   │   ├── error.tsx               # Global error boundary
│   │   │
│   │   ├── discover/
│   │   │   ├── layout.tsx          # Discover shell: FilterSidebar + main content area
│   │   │   ├── page.tsx            # /discover → gift grid (Server Component, RSC data fetch)
│   │   │   └── loading.tsx         # Skeleton grid (Suspense boundary)
│   │   │
│   │   ├── item/
│   │   │   └── [id]/
│   │   │       ├── page.tsx        # /item/[id] → Server Component: detail + similar
│   │   │       ├── loading.tsx
│   │   │       └── opengraph-image.tsx  # Dynamic OG image for sharing
│   │   │
│   │   ├── search/
│   │   │   ├── page.tsx            # /search → AI search entry point (Client Component)
│   │   │   └── loading.tsx
│   │   │
│   │   ├── wishlists/
│   │   │   ├── page.tsx            # /wishlists → user's lists (requires auth)
│   │   │   ├── [id]/
│   │   │   │   ├── page.tsx        # /wishlists/[id] → shareable list view
│   │   │   │   └── loading.tsx
│   │   │   └── layout.tsx          # Auth guard wrapper
│   │   │
│   │   ├── auth/
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   └── register/
│   │   │       └── page.tsx
│   │   │
│   │   └── admin/
│   │       ├── layout.tsx          # Admin shell: sidebar nav + admin auth guard
│   │       ├── page.tsx            # /admin → dashboard overview stats
│   │       ├── queue/
│   │       │   ├── page.tsx        # /admin/queue → review queue table
│   │       │   └── [id]/
│   │       │       └── page.tsx    # /admin/queue/[id] → single item review
│   │       ├── taxonomy/
│   │       │   ├── page.tsx        # /admin/taxonomy → tag type + tag management
│   │       │   └── [tag_type_id]/
│   │       │       └── page.tsx    # /admin/taxonomy/[tag_type_id] → tags list
│   │       ├── ingestion/
│   │       │   └── page.tsx        # /admin/ingestion → cron table + manual triggers
│   │       └── items/
│   │           ├── page.tsx        # /admin/items → full item list
│   │           ├── new/
│   │           │   └── page.tsx    # /admin/items/new → manual item form
│   │           └── [id]/
│   │               └── page.tsx    # /admin/items/[id] → edit form
│   │
│   ├── components/
│   │   ├── ui/                     # Primitive/design-system components (shadcn/ui pattern)
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Select.tsx
│   │   │   ├── Badge.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Dialog.tsx
│   │   │   ├── Toast.tsx
│   │   │   ├── Skeleton.tsx
│   │   │   ├── DataTable.tsx       # Generic TanStack Table wrapper
│   │   │   └── Pagination.tsx
│   │   │
│   │   ├── gift/                   # Domain: gift catalog
│   │   │   ├── GiftCard.tsx        # Grid item: image, title, price, tag badges, wishlist btn
│   │   │   ├── GiftGrid.tsx        # Responsive grid container + skeleton fallback
│   │   │   ├── GiftDetail.tsx      # Full item page content
│   │   │   ├── SimilarItems.tsx    # Horizontal scroll row
│   │   │   └── PriceDisplay.tsx
│   │   │
│   │   ├── discovery/
│   │   │   ├── FilterPanel.tsx     # Collapsible sidebar: all filter controls
│   │   │   ├── FilterChips.tsx     # Active filter pills with remove buttons
│   │   │   ├── RecipientProfileForm.tsx  # Guided: age, relationship, occasion, interests, budget
│   │   │   ├── OccasionPicker.tsx
│   │   │   ├── BudgetRangeSlider.tsx
│   │   │   └── SortSelect.tsx
│   │   │
│   │   ├── search/
│   │   │   ├── SearchBar.tsx       # Debounced text input → triggers AI or text search
│   │   │   ├── SearchResults.tsx
│   │   │   └── SearchInterpretation.tsx  # Renders AI's natural-language explanation
│   │   │
│   │   ├── wishlist/
│   │   │   ├── WishlistCard.tsx
│   │   │   ├── WishlistItemRow.tsx
│   │   │   ├── AddToWishlistButton.tsx   # Heart icon; optimistic update; dropdown if multiple lists
│   │   │   ├── CreateWishlistModal.tsx
│   │   │   └── ShareWishlistButton.tsx   # Copy link UX
│   │   │
│   │   ├── admin/
│   │   │   ├── ReviewCard.tsx            # Queue item: image + metadata + approve/reject
│   │   │   ├── ReviewActions.tsx         # Keyboard-shortcut-aware approve/reject bar
│   │   │   ├── BulkActionBar.tsx         # Floating bar: "N selected — Approve All / Reject All"
│   │   │   ├── TaxonomyEditor.tsx        # Inline editable tag rows
│   │   │   ├── CronScheduleTable.tsx     # Cron list with toggle + trigger buttons
│   │   │   ├── IngestionTriggerPanel.tsx # Scraper + Instagram trigger forms
│   │   │   ├── CsvUploadZone.tsx         # Drag-and-drop CSV upload with row-error display
│   │   │   ├── ItemForm.tsx              # Shared create/edit form for manual items
│   │   │   └── JobStatusBadge.tsx        # Live-polling badge for running jobs
│   │   │
│   │   ├── layout/
│   │   │   ├── Navbar.tsx
│   │   │   ├── AdminSidebar.tsx
│   │   │   ├── Footer.tsx
│   │   │   └── AuthGuard.tsx             # Client-side route guard wrapper
│   │   │
│   │   └── providers/
│   │       ├── QueryProvider.tsx         # TanStack Query client + devtools
│   │       ├── AuthProvider.tsx          # Zustand auth store initializer
│   │       └── ToastProvider.tsx         # Sonner toast context
│   │
│   ├── hooks/                       # React Query hooks per domain
│   │   ├── useItems.ts
│   │   ├── useItemDetail.ts
│   │   ├── useSearch.ts
│   │   ├── useAiSearch.ts
│   │   ├── useWishlists.ts
│   │   ├── useWishlistMutations.ts
│   │   ├── useRecommendations.ts
│   │   ├── useAdminQueue.ts
│   │   ├── useAdminTaxonomy.ts
│   │   ├── useAdminIngestion.ts
│   │   ├── useAdminCron.ts
│   │   └── useAuth.ts
│   │
│   ├── stores/                      # Zustand stores
│   │   ├── filterStore.ts           # Discovery filters (persisted to URL via nuqs)
│   │   ├── authStore.ts             # User session, tokens
│   │   ├── wishlistStore.ts         # Optimistic wishlist item set
│   │   └── adminStore.ts            # Selected queue items for bulk actions
│   │
│   ├── lib/
│   │   ├── api/                     # Generated + hand-rolled API clients
│   │   │   ├── generated/           # @hey-api/openapi-ts output
│   │   │   └── client.ts            # Axios/fetch wrapper: auth headers, refresh logic
│   │   ├── utils.ts                 # cn(), formatPrice(), formatDate()
│   │   └── validations.ts           # Zod schemas for forms
│   │
│   └── types/
│       ├── api.ts                   # Re-exports from generated client
│       └── filters.ts               # FilterState type
```

---

### 2.2 Component Hierarchy

#### `/discover` Page

```
DiscoverPage (Server Component — fetches initial page SSR)
└── DiscoverLayout (layout.tsx)
    ├── FilterPanel (Client Component — controlled by filterStore)
    │   ├── RecipientProfileForm
    │   │   ├── AgeRangeInput
    │   │   ├── RelationshipSelect
    │   │   ├── OccasionPicker (multi-select tag chips)
    │   │   └── BudgetRangeSlider
    │   ├── InterestTagPicker (checkbox tree grouped by TagType)
    │   └── SortSelect
    ├── FilterChips  (shows active filters; each chip removes filter from store)
    └── GiftGrid (Client Component — React Query, re-fetches on filter changes)
        ├── GiftCard × N
        │   ├── Image (next/image, lazy)
        │   ├── PriceDisplay
        │   ├── TagBadge × M
        │   └── AddToWishlistButton
        └── Pagination / InfiniteScroll trigger
```

#### `/item/[id]` Page

```
ItemDetailPage (Server Component — generateMetadata for SEO)
├── GiftDetail
│   ├── ImageGallery (Client Component — swipe carousel)
│   ├── PriceDisplay
│   ├── TagBadge[] (occasions + interests)
│   ├── AddToWishlistButton
│   ├── AffiliateLink ("Buy on [Retailer]" CTA)
│   └── RecipientProfileBadge (age range, occasions)
└── SimilarItems (deferred Client Component)
    └── GiftCard × 5
```

#### `/admin/queue` Page

```
ReviewQueuePage (Client Component — needs real-time updates)
├── BulkActionBar (floats when selection > 0, from adminStore)
├── QueueFilters (status tabs + source filter)
└── ReviewTable (DataTable)
    └── ReviewCard × N
        ├── ItemThumbnail
        ├── ItemMetadataGrid (title, price, source, detected tags)
        ├── TagEditor (inline: add/remove tags before approving)
        └── ReviewActions
            ├── ApproveButton  [keyboard: A]
            ├── RejectButton   [keyboard: R]
            └── SkipButton     [keyboard: S / →]
```

#### `/admin/ingestion` Page

```
IngestionPage
├── CronScheduleTable
│   └── CronScheduleRow × N
│       ├── SiteName + CronExpression
│       ├── LastRunAt + NextRunAt
│       ├── JobStatusBadge (polls /scraper/jobs/{id} every 5s while running)
│       ├── EnableToggle
│       └── TriggerNowButton
├── IngestionTriggerPanel
│   ├── ScraperTriggerForm  (select site → POST /ingestion/scraper/trigger)
│   └── InstagramTriggerForm (target input + type radio)
└── CsvUploadZone
    ├── DropZone
    ├── CsvPreviewTable (first 5 rows)
    └── ImportResultPanel (accepted/rejected counts + error rows)
```

---

### 2.3 State Management

#### Zustand Stores

```typescript
// stores/filterStore.ts
// Synced to URL search params via nuqs for shareable filter URLs
interface FilterState {
  ageMin: number | null
  ageMax: number | null
  relationship: string | null
  occasions: string[]         // tag slugs
  interests: string[]         // tag slugs
  budgetMin: number | null
  budgetMax: number | null
  sort: SortOption
  // Actions
  setFilter: <K extends keyof FilterState>(key: K, value: FilterState[K]) => void
  resetFilters: () => void
  removeOccasion: (slug: string) => void
  removeInterest: (slug: string) => void
}

// stores/wishlistStore.ts
// Tracks item IDs currently in any wishlist for instant heart-icon feedback
interface WishlistStore {
  wishedItemIds: Set<string>
  pendingAdd: Set<string>      // items awaiting server confirmation
  pendingRemove: Set<string>
  // Populated on mount from /wishlists API
  hydrate: (itemIds: string[]) => void
  optimisticAdd: (itemId: string) => void
  optimisticRemove: (itemId: string) => void
  confirmAdd: (itemId: string) => void
  confirmRemove: (itemId: string) => void
  rollbackAdd: (itemId: string) => void
  rollbackRemove: (itemId: string) => void
}

// stores/authStore.ts
interface AuthStore {
  user: UserOut | null
  accessToken: string | null
  isAuthenticated: boolean
  isAdmin: boolean
  setSession: (user: UserOut, accessToken: string) => void
  clearSession: () => void
}

// stores/adminStore.ts
// For review queue bulk actions
interface AdminStore {
  selectedQueueIds: Set<string>
  toggleSelect: (id: string) => void
  selectAll: (ids: string[]) => void
  clearSelection: () => void
}
```

#### React Query (TanStack Query) — Server State

```typescript
// hooks/useItems.ts
export function useItems(filters: FilterState) {
  return useInfiniteQuery({
    queryKey: ["items", filters],
    queryFn: ({ pageParam }) =>
      itemsApi.listItems({ ...filtersToParams(filters), cursor: pageParam }),
    getNextPageParam: (lastPage) => lastPage.next_cursor,
    staleTime: 60_000,          // 1 min — discovery results don't need to be real-time
  })
}

// hooks/useAiSearch.ts
export function useAiSearch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { query: string; profile: RecipientProfile }) =>
      searchApi.aiSearch(payload),
    onSuccess: (data) => {
      // Pre-populate item detail cache from search results
      data.items.forEach((item) => {
        queryClient.setQueryData(["item", item.id], item)
      })
    },
  })
}

// hooks/useWishlistMutations.ts — optimistic updates
export function useAddToWishlist() {
  const queryClient = useQueryClient()
  const { optimisticAdd, confirmAdd, rollbackAdd } = useWishlistStore()

  return useMutation({
    mutationFn: ({ wishlistId, itemId }: { wishlistId: string; itemId: string }) =>
      wishlistApi.addItem(wishlistId, { item_id: itemId }),
    onMutate: ({ itemId }) => {
      optimisticAdd(itemId)           // immediately fill heart icon
      return { itemId }
    },
    onSuccess: (_, { itemId }) => confirmAdd(itemId),
    onError: (_, __, ctx) => {
      if (ctx) rollbackAdd(ctx.itemId)  // revert if request fails
      toast.error("Could not add to wishlist")
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["wishlists"] })
    },
  })
}
```

#### URL as Filter State (nuqs)

Filter state is serialized into URL search params using `nuqs` (Next.js-aware `useSearchParams` wrapper). This means:
- Filters survive page refresh.
- Users can share a filtered discovery URL.
- Browser back/forward navigation restores filter state.
- Server Components receive filter state on initial SSR (no hydration flash).

```typescript
// stores/filterStore.ts — URL binding
import { useQueryStates, parseAsInteger, parseAsArrayOf, parseAsString } from "nuqs"

export function useFilterParams() {
  return useQueryStates({
    ageMin:       parseAsInteger,
    ageMax:       parseAsInteger,
    relationship: parseAsString,
    occasions:    parseAsArrayOf(parseAsString),
    interests:    parseAsArrayOf(parseAsString),
    budgetMin:    parseAsInteger,
    budgetMax:    parseAsInteger,
    sort:         parseAsString.withDefault("relevance"),
  })
}
```

---

### 2.4 API Integration

#### OpenAPI TypeScript Client Generation

```typescript
// openapi-ts.config.ts
import { defineConfig } from "@hey-api/openapi-ts"

export default defineConfig({
  input: "http://localhost:8000/openapi.json",   // pulled from FastAPI at build time
  output: "src/lib/api/generated",
  plugins: [
    "@hey-api/client-fetch",
    "@tanstack/react-query",                      // generates query key factories
  ],
})
```

This generates:
- Fully-typed request/response models matching Pydantic schemas
- Query key factories for React Query cache invalidation
- A fetch client that can be configured with interceptors

#### Auth-Aware HTTP Client

```typescript
// lib/api/client.ts
import { client } from "./generated/client"
import { useAuthStore } from "@/stores/authStore"

client.setConfig({
  baseUrl: process.env.NEXT_PUBLIC_API_URL,
})

// Request interceptor: attach Bearer token
client.interceptors.request.use((request) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    request.headers.set("Authorization", `Bearer ${token}`)
  }
  return request
})

// Response interceptor: handle 401 → refresh → retry once
client.interceptors.response.use(async (response) => {
  if (response.status === 401) {
    const refreshed = await attemptTokenRefresh()
    if (refreshed) {
      // Retry original request with new token
      return client.request(response.request)
    } else {
      useAuthStore.getState().clearSession()
      window.location.href = "/auth/login"
    }
  }
  return response
})
```

#### React Query Hooks — All Domains

```typescript
// hooks/useAdminQueue.ts
export const useReviewQueue = (filters: QueueFilters) =>
  useQuery({
    queryKey: adminQueryKeys.queue(filters),
    queryFn: () => adminApi.listQueue(filters),
    refetchInterval: 10_000,          // auto-refresh for live queue updates
  })

export const useApproveItem = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ queueId, patch }: ApprovePayload) =>
      adminApi.approveQueueItem(queueId, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminQueryKeys.queue._def })
      toast.success("Item approved")
    },
  })
}

export const useBulkApprove = () => {
  const qc = useQueryClient()
  const clearSelection = useAdminStore((s) => s.clearSelection)
  return useMutation({
    mutationFn: (queueIds: string[]) => adminApi.bulkApprove({ queue_ids: queueIds }),
    onSuccess: ({ accepted, rejected }) => {
      qc.invalidateQueries({ queryKey: adminQueryKeys.queue._def })
      clearSelection()
      toast.success(`Approved ${accepted}, skipped ${rejected}`)
    },
  })
}
```

---

### 2.5 Admin Panel UX

#### Review Queue Workflow

The review queue is designed for high-throughput moderation. The UX mirrors email triage tools (Gmail-style):

**Keyboard shortcuts** (registered globally on `/admin/queue`):
```
A           → Approve focused item
R           → Reject focused item (opens reason modal)
S / →       → Skip to next item
← / P       → Go to previous item
Space       → Toggle select current item
Ctrl+A      → Select all visible items
Ctrl+Enter  → Bulk approve selected
Escape      → Clear selection / close modal
```

Implementation:
```typescript
// components/admin/ReviewActions.tsx
useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    if (document.activeElement?.tagName === "INPUT") return  // don't capture in forms
    if (e.key === "a" && !e.ctrlKey) approveItem(focusedId)
    if (e.key === "r") setRejectModalOpen(true)
    if (e.key === "s" || e.key === "ArrowRight") advanceFocus()
    if (e.key === "ArrowLeft" || e.key === "p") retreatFocus()
  }
  window.addEventListener("keydown", handler)
  return () => window.removeEventListener("keydown", handler)
}, [focusedId])
```

**Bulk action bar:**
- Floats at bottom of screen when `selectedQueueIds.size > 0`.
- Shows count: "14 items selected".
- "Approve All" and "Reject All" buttons with confirmation for reject.
- "Clear Selection" link.

**Inline tag editing before approval:**
Each queue item card has an editable tag zone. Admin can add/remove tags inline before clicking Approve. The `item_patch` payload sent to `/approve` carries the corrected tag list.

#### Taxonomy Inline Editor

```
TagTypeRow (expandable)
└── TagRow × N
    ├── Name (click-to-edit inline Input)
    ├── Slug (auto-generated from name, editable)
    ├── Item count badge
    ├── Merge button → opens MergeTagModal (target dropdown)
    └── Delete button (disabled if item count > 0)
```

Edits are debounced (500ms) then committed via `PATCH /taxonomy/tags/{id}`. Optimistic updates show the change immediately; errors revert.

#### Cron Schedule Management

The `CronScheduleTable` shows:
- Human-readable cron description (using `cronstrue` library: `"0 2 * * *"` → `"At 02:00 AM"`)
- Last run status (badge: success/failed/running)
- Next scheduled run countdown
- Live job progress for running scrapes: `JobStatusBadge` polls `/scraper/jobs/{job_id}` every 5 seconds and shows a progress bar during active scrapes.

---

## 3. Cross-Cutting Concerns

### 3.1 Error Handling

#### Backend Error Hierarchy

```python
# core/exceptions.py
class GiftFinderError(Exception):
    """Base domain exception."""
    status_code: int = 500
    code: str = "internal_error"

class NotFoundError(GiftFinderError):
    status_code = 404
    code = "not_found"

class ValidationError(GiftFinderError):
    status_code = 422
    code = "validation_error"

class AuthError(GiftFinderError):
    status_code = 401
    code = "unauthorized"

class ForbiddenError(GiftFinderError):
    status_code = 403
    code = "forbidden"

class ConflictError(GiftFinderError):
    status_code = 409
    code = "conflict"

class AdapterError(GiftFinderError):
    """Raised by scraper adapters on unrecoverable failure."""
    status_code = 502
    code = "adapter_error"

class RateLimitError(GiftFinderError):
    status_code = 429
    code = "rate_limited"
```

#### FastAPI Exception Handlers

```python
# main.py
from fastapi.responses import JSONResponse

@app.exception_handler(GiftFinderError)
async def domain_exception_handler(request: Request, exc: GiftFinderError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code":    exc.code,
                "message": str(exc),
                "request_id": request.state.request_id,  # set by middleware
            }
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code":    "validation_error",
                "message": "Request validation failed",
                "details": exc.errors(),     # field-level error list
                "request_id": request.state.request_id,
            }
        },
    )
```

#### Frontend Error Handling Flow

```
API call fails
  → React Query catches error
  → onError callback fires
    → Structured error: { error: { code, message, details } }
    → toast.error(error.message)  via Sonner
    → If code === "unauthorized" → redirect to /auth/login
    → If code === "rate_limited" → show retry countdown
  → Component reads isError + error from useQuery/useMutation
    → Renders inline error state (e.g., "Failed to load items — Retry")
```

**Error boundary per route segment:**
```typescript
// app/discover/error.tsx
"use client"
export default function DiscoverError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 py-20">
      <p className="text-destructive">{error.message}</p>
      <Button onClick={reset}>Try again</Button>
    </div>
  )
}
```

---

### 3.2 Security

#### JWT & Auth Security
- Access tokens: 15-minute expiry, never stored in `localStorage` (use memory/httpOnly cookie).
- Refresh tokens: httpOnly + Secure + SameSite=Strict cookie only.
- Token rotation on every refresh call; old JTI invalidated in Redis.
- Login rate limiting: `slowapi` — 5 requests / 15 min / IP.

#### CORS Configuration
```python
# main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,    # ["https://giftfinder.com"] in prod
    allow_credentials=True,                    # required for httpOnly cookie refresh
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
```

#### Input Validation
- All request bodies validated by Pydantic with strict mode (`model_config = ConfigDict(strict=True)`).
- File uploads: validate MIME type from file bytes (not just `Content-Type` header) using `python-magic`. Accept only `image/jpeg`, `image/png`, `image/webp`.
- Max file size enforced at middleware level (10 MB default).
- CSV imports: row-by-row Pydantic validation; malformed rows are collected and returned as errors, not silently skipped.

#### Admin Route Protection
- Backend: `require_admin` dependency on all `/api/v1/admin/**` routes.
- Frontend: `AdminSidebar` layout checks `useAuthStore().isAdmin`; server-side, Next.js middleware validates JWT before rendering admin routes.

```typescript
// middleware.ts (Next.js)
export function middleware(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value
  const isAdminRoute = request.nextUrl.pathname.startsWith("/admin")
  const isAuthRoute = request.nextUrl.pathname.startsWith("/auth")

  if (isAdminRoute) {
    if (!token) return NextResponse.redirect(new URL("/auth/login", request.url))
    const payload = verifyJwtEdge(token)  // lightweight edge-compatible verify
    if (!payload || payload.role !== "admin") {
      return NextResponse.redirect(new URL("/", request.url))
    }
  }
  return NextResponse.next()
}
```

#### Rate Limiting on Ingestion Triggers
```python
# api/v1/admin/ingestion.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/scraper/trigger")
@limiter.limit("10/minute")              # prevent accidental scrape storms
async def trigger_scraper(...): ...

@router.post("/instagram/trigger")
@limiter.limit("5/minute")              # Instagram API is quota-constrained
async def trigger_instagram(...): ...
```

#### S3 Image Upload Security
- Pre-signed upload URLs via `boto3.generate_presigned_post()` with:
  - `ContentType` condition (image/* only)
  - Max size condition (10 MB)
  - 5-minute URL expiry
- Uploaded images are served via CloudFront, never directly from S3.
- Server-side image re-encode (via Pillow) strips EXIF data and validates image structure before storing final URL.

---

### 3.3 Observability

#### Structured Logging (structlog)

```python
# core/logging.py
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,   # request_id, user_id from context
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

log = structlog.get_logger()

# Usage in service
log.info(
    "item.scraped",
    site_id=str(site_id),
    item_count=len(results),
    new_items=new_count,
    job_id=str(job_id),
)
```

**Request ID middleware:**
```python
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    structlog.contextvars.clear_contextvars()
    return response
```

#### Celery Task Monitoring

- **Flower** dashboard deployed alongside workers (`celery flower --broker=redis://...`).
- Task state stored in Redis result backend with 24-hour TTL.
- `scraper_jobs` table gives persistent job history visible in admin panel (unlike Flower which is ephemeral).
- Alert thresholds (via Celery signals → structlog → log aggregator):
  - Task `time_limit` exceeded → log CRITICAL
  - 3 consecutive retries exhausted → log ERROR + write to `ingestion_log` with `status="failed"`
  - Queue depth > 100 tasks → log WARNING

#### Key Metrics to Track

| Metric | Source | Alert Threshold |
|--------|--------|----------------|
| Scraper success rate | `scraper_jobs` | < 80% over 1hr window |
| Embedding queue depth | Redis queue length | > 500 |
| Instagram API usage % | Response header → log | > 80% |
| p99 API latency | Middleware timer → log | > 2s |
| Review queue depth | `review_queue` count | > 1000 pending |
| DB connection pool | SQLAlchemy events | > 90% utilized |

---

### 3.4 Risk Assessment

#### Risk 1: Instagram API Rate Limits

**Description:** The Meta Graph API enforces per-app usage quotas (`call_count`, `total_time`, `total_cputime`). Exceeding 100% triggers a 1-hour block. Hashtag search has additional restrictions (only 30 unique hashtags per business account per week).

**Mitigations:**
1. Parse `X-App-Usage` and `X-Business-Use-Case-Usage` headers on every response. If any metric > 80%, pause the `instagram_fetch_task` and schedule retry after 15 minutes.
2. Use Celery `rate_limit="10/m"` on `instagram_fetch_task` to self-limit below API quota.
3. Cache API responses in Redis (TTL 30 min) to avoid redundant calls.
4. Use webhooks (Instagram Subscription API) for real-time updates instead of polling where possible.
5. Rotate multiple Meta App credentials if volume demands it (with separate business accounts).

---

#### Risk 2: Scraper Fragility

**Description:** HTML scrapers break silently when target sites change DOM structure. This causes empty or malformed data entering the catalog without immediate visibility.

**Mitigations:**
1. Each adapter has a `health_check()` method run before full scrape. If it returns `False`, abort and create a `status="failed"` job with a `structure_changed` error code.
2. Monitor `items_found` per job: if a site that normally yields 200 items returns < 10, trigger an alert.
3. Generic fallback adapter (`generic_html.py`) uses configurable CSS selectors stored in `scraper_sites.config` — site structure changes can be patched by updating config without a code deploy.
4. All scraped items go to `pending_review` status by default. Zero items auto-published from scrapers.
5. Weekly automated health-check cron runs `health_check()` on all adapters and emails report.

---

#### Risk 3: OpenAI Embedding Costs

**Description:** At $0.00002/1K tokens for `text-embedding-3-small`, 100K items × 500 tokens ≈ $1,000 initial load. Ongoing costs for re-embedding on content changes can grow unpredictably.

**Mitigations:**
1. **Batch embeddings:** Use OpenAI's array input to embed up to 100 items per API call, reducing per-item overhead.
2. **Embed only meaningful text:** Title + description, capped at 512 tokens. Skip boilerplate legal/shipping text.
3. **Re-embed only on content change:** Compare `sha256(title + description)` before calling OpenAI. Only re-embed if text changed.
4. **Cache embeddings:** If the same product appears from multiple scrapers, the content hash match prevents duplicate embedding calls.
5. **Budget guard:** A Redis counter tracks daily embedding API spend. If it exceeds a configurable threshold (e.g., $50/day), new embed tasks are queued but not dispatched until the next day.

---

#### Risk 4: Recommendation Cold Start

**Description:** New users have no interaction history. The collaborative filter produces random or popularity-biased results, which may not engage the user.

**Mitigations:**
1. **Profile-based bootstrap:** At registration, collect a brief `RecipientProfile` (or "who are you shopping for today?"). Use this as a content-based filter: immediate ANN search over the embedding space without needing personal history.
2. **Popularity fallback:** When `recommendation_signals` is empty or stale, fall back to `items ORDER BY interaction_count DESC` filtered by profile.
3. **Implicit signals from first session:** Record `view` interactions immediately (no login required via anonymous session ID). Persist these to the user's history on registration.
4. **Trending section:** Curated "popular this week" section on the home page serves as social proof and bypasses personalization entirely for new users.
5. **Progressive enrichment:** After 5 wishlist adds or 20 views, mark the user as "warm" and switch to the embedding-based recommender.

---

#### Risk 5: pgvector Index Performance

**Description:** ANN search on a 1-million-row table with `vector(1536)` using `ivfflat` can have high recall/performance trade-offs. Index build time can block table during maintenance. Query latency degrades without proper tuning.

**Mitigations:**
1. **Index configuration:**
   ```sql
   CREATE INDEX items_embedding_ivfflat_idx
     ON items USING ivfflat (embedding vector_cosine_ops)
     WITH (lists = 200);   -- sqrt(N) for N=40K; re-tune as data grows
   ```
2. **HNSW for better recall:** At >500K rows, migrate to HNSW index (`USING hnsw`) which trades memory for higher recall and eliminates the need to tune `lists`. Build HNSW concurrently (`CREATE INDEX CONCURRENTLY`) to avoid table lock.
3. **Pre-filter before ANN:** Apply hard SQL filters (price range, status=active, tag filters) using a CTE or subquery before the vector search to reduce the candidate set. pgvector supports filtered ANN via `WHERE` clause.
4. **Partial index on active items:**
   ```sql
   CREATE INDEX items_embedding_active_idx
     ON items USING ivfflat (embedding vector_cosine_ops)
     WHERE status = 'active';
   ```
5. **`probes` tuning:** Set `SET ivfflat.probes = 10` at query time for higher recall (default is 1). Benchmark at target item counts to find the latency/recall sweet spot.

---

## Appendix A: Docker Compose (Development)

```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: giftfinder
      POSTGRES_USER: giftfinder
      POSTGRES_PASSWORD: secret
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports: ["5432:5432"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  api:
    build:
      context: ./backend
      dockerfile: docker/Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://giftfinder:secret@db/giftfinder
      REDIS_URL: redis://redis:6379/0
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      S3_BUCKET: ${S3_BUCKET}
    ports: ["8000:8000"]
    depends_on: [db, redis]
    volumes:
      - ./backend:/app

  worker-scraping:
    build:
      context: ./backend
      dockerfile: docker/Dockerfile.worker
    command: celery -A app.workers.celery_app worker -Q scraping -c 4 -l INFO
    environment: *api-env
    depends_on: [db, redis]

  worker-embeddings:
    build:
      context: ./backend
      dockerfile: docker/Dockerfile.worker
    command: celery -A app.workers.celery_app worker -Q embeddings -c 8 -l INFO
    environment: *api-env
    depends_on: [db, redis]

  worker-general:
    build:
      context: ./backend
      dockerfile: docker/Dockerfile.worker
    command: celery -A app.workers.celery_app worker -Q ingestion,recommendations -c 4 -l INFO
    environment: *api-env
    depends_on: [db, redis]

  beat:
    build:
      context: ./backend
      dockerfile: docker/Dockerfile.worker
    command: celery -A app.workers.celery_app beat -l INFO --scheduler redbeat.RedBeatScheduler
    environment: *api-env
    depends_on: [redis]

  flower:
    image: mher/flower:2.0
    command: celery flower --broker=redis://redis:6379/0
    ports: ["5555:5555"]
    depends_on: [redis]

  frontend:
    build:
      context: ./frontend
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    ports: ["3000:3000"]
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next

volumes:
  pgdata:
```

---

## Appendix B: Key Technology Versions

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.12 | for `asyncio.TaskGroup`, improved `tomllib` |
| FastAPI | 0.115+ | lifespan context manager, annotated dependencies |
| SQLAlchemy | 2.0 | fully async, `mapped_column` style |
| Alembic | 1.13+ | async support |
| Celery | 5.4+ | Redis broker, result backend |
| celery-redbeat | 2.2+ | Redis-backed dynamic beat scheduler |
| Next.js | 14 (App Router) | Server Components, parallel routes |
| TypeScript | 5.4+ | |
| TanStack Query | 5.x | `useInfiniteQuery` v5 API |
| Zustand | 4.x | |
| nuqs | 1.x | URL search param state |
| @hey-api/openapi-ts | latest | OpenAPI → TS client codegen |
| pgvector | 0.7+ | HNSW index support |
| openai | 1.x | Python async client |
