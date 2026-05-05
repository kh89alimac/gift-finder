# Architecture Decision Records

This document records the five most consequential design decisions made during the Gift Finder build. Each ADR follows the standard format: Context → Decision → Consequences.

---

## ADR-001: Unified `items` table with `source` and `status` enums

**Status**: Accepted

### Context

Gift Finder has three distinct ingestion pipelines: web scrapers, Instagram Graph API, and manual admin entry. The natural first instinct is to give each source its own table (`scraped_items`, `instagram_items`, `manual_items`) to isolate schemas and avoid null columns.

However, the product requires:
- A single discovery feed mixing items from all three sources
- A unified review queue
- Cross-source "similar items" recommendations
- Admin tools that operate on any item regardless of origin

Managing three tables would mean every downstream query (discovery, search, recommendations) must UNION across sources, recommendation signals would need to reference three foreign keys, and every schema change would be replicated three times.

### Decision

All items live in a single `items` table. The `source` column (ENUM: `scraper`, `instagram`, `manual`, `csv_import`) records provenance, and the `status` column (ENUM: `pending_review`, `active`, `rejected`, `archived`) drives the item's lifecycle state machine regardless of source.

Provenance fields (`source_site_id`, `source_external_id`, `source_url`) are nullable, populated only when the source provides them. Source-specific metadata that does not belong in the main row (e.g., Instagram `raw_data`) lives in the corresponding side table (`instagram_queue`) that holds a `promoted_item_id` FK back to `items`.

The dedup constraint — `UNIQUE NULLS NOT DISTINCT (source_site_id, source_external_id)` — prevents the same product from being ingested twice from the same site while correctly handling manual items that have no `source_site_id`.

### Consequences

**Positive:**
- Discovery, search, and recommendation queries are single-table; no UNION complexity.
- The review queue works identically for all sources — one `review_queue` table with a `source` column.
- Cross-source recommendations are trivial: `recommendation_signals` references tags, not items, so a user's affinity for "Travel" applies equally to scraped, Instagram-sourced, and manually-entered travel gifts.
- Adding a fourth source (`csv_import`) required only adding one enum value and no new table.

**Negative / risks:**
- The `status` state machine must be enforced in application code, not database constraints. A stray UPDATE could set an `archived` item back to `active`. Mitigation: all status transitions go through service-layer methods that validate the transition.
- Some nullable columns will always be NULL for certain sources (e.g., `source_site_id` is always NULL for manual items). This is an accepted tradeoff; the columns are indexed with partial indexes that skip NULLs.

---

## ADR-002: pgvector for AI semantic search (not Elasticsearch or Pinecone)

**Status**: Accepted

### Context

The AI search feature requires vector similarity search to find gifts semantically related to a natural-language query. Three options were seriously evaluated:

1. **Elasticsearch** (with dense vector fields): mature, feature-rich, good hybrid search, but requires a separate cluster, an operational team to manage it, and introduces a sync problem between PostgreSQL and Elasticsearch.

2. **Pinecone** (managed vector database): zero-ops, excellent at ANN, but means storing embeddings in a completely separate system from all other data. Every recommendation and search query requires two datastores. Monthly cost scales with vector count.

3. **pgvector** (PostgreSQL extension): embeddings stored directly in the `items.embedding` column alongside all other item data. Queries can combine vector similarity with relational filters (price range, tag filters, status) in a single SQL statement with no cross-system joins.

The product is a single-tenant application with an existing PostgreSQL deployment. Adding Elasticsearch or Pinecone would be two new infrastructure dependencies for a feature that can be served from the database that already exists.

### Decision

Use pgvector with an HNSW index (migration 002). Embeddings are 1536-dimensional vectors produced by OpenAI `text-embedding-3-small`. The HNSW index is a partial index scoped to `status='active' AND embedding IS NOT NULL` to minimize index size and memory usage.

Hybrid search combines pgvector ANN (top-K by cosine similarity) with full-text tsvector filtering, re-ranked by a weighted score that favors semantic closeness while preserving textual precision.

### Consequences

**Positive:**
- Zero additional infrastructure. Vector search is a `<->` operator in the same query that already filters by price and tags.
- Embeddings are co-located with item data; there is no sync lag or eventual consistency between a primary store and a vector store.
- HNSW gives stable recall under continuous inserts without periodic `REINDEX` (unlike IVFFlat, which requires rebalancing as the corpus grows).
- Natural hybrid queries: `WHERE price < 100 AND status = 'active' ORDER BY embedding <-> $1 LIMIT 50` — filter first, then rank by vector similarity.

**Negative / risks:**
- pgvector is not a dedicated vector database. At tens of millions of embeddings, query latency and memory usage will increase in ways that Pinecone would not. Mitigation: the partial HNSW index and a 50-result limit cap keep latency under 50ms at current corpus size.
- ANN, not exact nearest-neighbor — the HNSW index may miss the true nearest neighbors for edge cases. Acceptable for gift recommendations; precision-critical search is not a hard requirement.
- Single point of coupling: the PostgreSQL database handles both OLTP and vector search load. Under extreme vector search volume, an index-heavy query could compete with write throughput. Mitigation: read replicas with pgvector can offload search queries if needed.

---

## ADR-003: Celery + Redis for background jobs (not a DB-backed queue)

**Status**: Accepted

### Context

Several operations are too slow for synchronous request handling:
- Web scraping (minutes to hours per site)
- OpenAI embedding generation (network latency per item)
- Instagram Graph API fetching (rate-limited, sequential)
- Recommendation signal recomputation (full-table aggregation)

Options considered:
1. **PostgreSQL-backed queue** (e.g., pgqueuer, SKIP LOCKED pattern): simple, no new infra, transactional. Limited by PostgreSQL write throughput for high-frequency job creation, no distributed worker coordination, no native retry semantics.
2. **Celery + Redis**: industry-standard, distributed workers, first-class retry/backoff, Flower monitoring dashboard, celery-redbeat for DB-backed cron schedules.
3. **AWS SQS + Lambda**: fully managed, scales to zero, but introduces AWS-specific coupling and makes local development harder.

The application already requires Redis for access token revocation (JTI blacklist). Adding Celery uses an already-present dependency with no new infrastructure.

### Decision

Celery with Redis as the broker and result backend. Four queues route tasks by priority:
- `default` — general purpose
- `scraping` — site scrape tasks
- `embedding` — OpenAI API calls
- `recommendations` — signal recomputation

celery-redbeat is used as the beat scheduler so cron schedules are stored in PostgreSQL (via `cron_schedules` table) and editable through the admin panel at runtime, rather than being hardcoded in a `celeryconfig.py` file.

### Consequences

**Positive:**
- Workers scale horizontally; a second worker node can be added with zero config changes.
- Celery's retry semantics (exponential backoff, max-retries, dead-letter behavior) handle transient failures in scraping and OpenAI calls without any custom code.
- Flower provides a real-time dashboard for monitoring task state, failure rates, and worker health.
- SKIP LOCKED pattern in scraper_jobs table provides an additional layer of job deduplication at the database level.

**Negative / risks:**
- Redis is a single point of failure. If Redis goes down, no new background tasks can be enqueued. Mitigation: Redis is configured with `appendonly yes` for AOF persistence; a replica can be promoted in under a minute.
- The broker and result backend share the same Redis instance. For very high task volumes, separating them (or using RabbitMQ as broker with Redis only for results) would be the next scaling step.
- Local development requires running Redis and a Celery worker alongside the FastAPI process. `docker compose up` handles this.

---

## ADR-004: Cursor pagination over offset pagination for the discovery feed

**Status**: Accepted

### Context

The discovery feed (`GET /items`) is the highest-traffic read path. The two standard pagination approaches:

1. **Offset pagination** (`LIMIT n OFFSET k`): simple, supports arbitrary page jumps, returns a total count. The problem: under frequent inserts, a row inserted between page 1 and page 2 requests causes page 2 to return one item that page 1 already showed (or skip an item). At page 50+ of a frequently-updated feed, `OFFSET 1200` scans and discards 1,200 rows — `O(n)` deep pages.

2. **Cursor pagination** (keyset): the cursor encodes the sort values of the last item on the previous page. The next query adds a `WHERE (published_at, id) < (cursor_published_at, cursor_id)` clause, which can use the partial index `ix_items_active_published` directly — `O(1)` regardless of page depth.

The discovery feed has frequent inserts (scrapers and Instagram ingestion add items continuously) and is expected to be browsed deeply (users exploring gift ideas browse many pages). Stable, consistent pagination is a UX requirement.

### Decision

Cursor on `(published_at DESC, id DESC)`. The cursor is encoded as opaque base64 JSON — clients treat it as an opaque string and never parse it. The encoding uses ISO-8601 datetimes and hex UUIDs to ensure clean round-trips. The `id` tiebreaker guarantees a strict total order even when multiple items share the same `published_at` timestamp.

Offset pagination is used in admin-only contexts (review queue, scraper job list) where the dataset is smaller, write frequency is lower, and total-count display is a usability requirement.

### Consequences

**Positive:**
- Page loads are `O(1)` regardless of depth — the index is used for every page.
- Stable pages: new items appearing at the top of the feed do not push existing items onto the wrong page for users mid-session.
- Shareable URLs: a cursor captured in a browser URL bar still returns the correct next page even after new items have been added.

**Negative / risks:**
- No total item count in cursor responses. If the UI needs to show "4,231 results", a separate `COUNT(*)` query is required (expensive on large tables; use `EXPLAIN` estimates or a materialized view for display purposes).
- No random page access ("jump to page 50"). Users must paginate forward sequentially. Acceptable for an infinite-scroll discovery feed.
- Cursors are opaque to clients but can be decoded (they are base64 JSON, not signed). This is a non-issue since the cursor only encodes publicly visible sort fields, not any private data.

---

## ADR-005: httpOnly cookie for refresh token, in-memory for access token

**Status**: Accepted

### Context

JWT tokens must be stored somewhere in the browser. Three common approaches:

1. **`localStorage`**: both tokens in `localStorage`. Simple. Vulnerable to XSS — any injected script can read `localStorage` and exfiltrate both tokens.

2. **httpOnly cookies for both tokens**: protects both from XSS. However, access tokens sent as cookies on every request require CSRF protection (double-submit cookie or `Synchronizer Token Pattern`). The backend must also handle cookie extraction on every authenticated endpoint, complicating stateless API design.

3. **Access token in memory, refresh token in httpOnly cookie**: access token lives only in Zustand (JavaScript in-memory state) — it is lost on tab close or page refresh, but the `POST /auth/refresh` call re-mints it from the cookie silently. The refresh token is in an httpOnly cookie scoped to `/api/v1/auth` so JavaScript cannot read it at all.

The application also implements token family rotation: each use of a refresh token invalidates the old one and issues a new one. If a stolen refresh token is reused, the rotation detects the family conflict and revokes all tokens in that family, limiting the blast radius of a credential theft.

### Decision

Access token: stored only in Zustand state (`authStore.ts`). The store is never persisted to `localStorage` or `sessionStorage`. The token is set in the `Authorization` header of every API request by the Axios client (`withCredentials: true` for cookie handling).

Refresh token: httpOnly `SameSite=Lax` cookie, `Secure=true` in production, scoped to `Path=/api/v1/auth`. The cookie is set/replaced by the server on login, register, and refresh. The client never sees it.

On page load, if the access token is absent (e.g., after a hard refresh), the frontend calls `POST /auth/refresh` before rendering protected pages. If the refresh cookie is expired or missing, the user is redirected to login.

Redis is used for JTI (JWT ID) revocation: revoked token JTIs are stored in Redis with TTL matching the token's expiry. This enables instant logout without waiting for the access token's 15-minute TTL to expire.

### Consequences

**Positive:**
- Access token cannot be exfiltrated by XSS — it never touches the DOM, `localStorage`, or `document.cookie`.
- Refresh token cannot be accessed by JavaScript at all — `httpOnly` means it is invisible to `document.cookie` and cannot be read by injected scripts.
- No CSRF risk on protected endpoints: the `Authorization: Bearer <token>` header is set explicitly by JavaScript code and cannot be sent by a forged cross-origin form submission (unlike a cookie-based auth scheme).
- Token family rotation + Redis JTI revocation provides a strong defense against refresh token theft.

**Negative / risks:**
- `withCredentials: true` must be set on all Axios requests, and the backend CORS configuration must explicitly allow the frontend origin with `allow_credentials=True`. A misconfigured CORS policy will silently drop the cookie.
- The access token is lost on hard page refresh. The silent `POST /auth/refresh` on page load adds one round-trip before the first authenticated request. Mitigation: the refresh call is initiated early (in `AuthProvider`) and awaited before rendering protected pages.
- If Redis goes down, token revocation (logout) stops working — users who log out appear to remain logged in until the access token's 15-minute TTL expires naturally. Mitigation: Redis persistence and a short access token lifetime (15 min) bound the worst-case window.
