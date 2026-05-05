# Testing & Validation: Gift Finder App

## Test Suite

### Files Created (15 test files, ~125 test functions)

**`backend/tests/conftest.py`**:
- PostgreSQL shims at import time — replaces ENUM, JSONB, TSVECTOR, ARRAY, UUID, Vector with SQLite-compatible equivalents
- Strips PG-specific `server_default` expressions so `Base.metadata.create_all` works on SQLite
- `_InMemoryRedis` implementing the full Redis API surface used by security.py
- `async_session` fixture: `autobegin=False` + rollback isolation per test
- `test_client` patches lifespan (ping_redis, dispose_engine, close_redis) — no real infra needed

**Unit tests** (`tests/unit/`) — 70 tests:
- `test_security.py` — bcrypt hashing, JWT encode/decode, expiry, token family rotation
- `test_item_service.py` — list_items filters/pagination/tag intersection, get_item_detail, record_interaction
- `test_search_service.py` — FTS delegation, AI hybrid fallback, OpenAI failure graceful degradation
- `test_wishlist_service.py` — CRUD, ConflictError on duplicate add, ForbiddenError for non-owner, share token
- `test_scraper_orchestrator.py` — content_hash determinism, auto_categorize, dedup, batch upsert
- `test_manual_ingestion.py` — MIME validation, EXIF-strip, CSV SAVEPOINT isolation, status on publish
- `test_review_queue_service.py` — approve/reject status transitions, bulk approve/reject partial failure
- `test_taxonomy_service.py` — merge_tags migration, dedup (already-tagged items), source deletion

**Integration tests** (`tests/integration/`) — 47 tests:
- `test_auth_endpoints.py` — register/login/refresh/me happy paths + error cases (409, 401)
- `test_items_endpoints.py` — discovery feed, budget filter, 404 on missing ID, AI search
- `test_wishlists_endpoints.py` — full CRUD, add/remove items, 403 for private wishlist non-owner
- `test_admin_endpoints.py` — 401/403 guards on all admin routes, approve/reject/bulk, CSV import
- `test_scraper_jobs.py` — claim_next_job status transitions, SKIP LOCKED, mark_completed/failed

**Migration tests** (`tests/test_migrations.py`) — 8 tests:
- Verifies all 15 expected tables exist
- Spot-checks column presence on critical tables
- Validates raw SQL INSERT/SELECT round-trips

**Run**: `cd backend && pip install -e ".[dev]" && pytest tests/ -v --cov=app --cov-report=term-missing`

---

## Security Findings

### Summary: 38 findings (4 CRITICAL, 11 HIGH, 11 MEDIUM, 9 LOW, 3 INFO)

### CRITICAL

| # | Finding | Location |
|---|---------|----------|
| C1 | Refresh token stored in localStorage instead of httpOnly cookie — entire family-rotation defence defeated by any XSS | `useAuth.ts`, `client.ts`, `auth.py` |
| C2 | CronSchedule `task_name` passed to `importlib.import_module` with no allowlist → RCE on admin compromise | `cron_scheduler_service.py` |
| C3 | Generic-HTML scraper and image URLs have no SSRF protection — AWS IMDS reachable from adapter | `generic_html.py`, `instagram_ingestion_service.py` |
| C4 | JWT secret `"change-me-in-production"` committed in docker-compose; no production guard in settings | `docker-compose.yml`, `config.py` |

### HIGH (selected)

| # | Finding | Location |
|---|---------|----------|
| H1 | Access tokens cannot be revoked — logout/role-demotion has no kill-switch for current access tokens | `security.py`, `auth_service.py` |
| H2 | No `is_active` flag on users — no account disable/lockout path | `user.py` |
| H3 | `item.product_url` rendered in `<a href>` without scheme validation — stored XSS via scraped data | `ItemDetailClient.tsx`, scraper pipeline |
| H4 | No CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy headers | `main.py`, `next.config.js` |
| H5 | `ApproveRequest.item_patch: dict[str, Any]` allows mass-assignment to any Item attribute | `review_queue.py`, `review_queue_service.py` |
| H6 | CSV import accepts raw `image_url`/`product_url` strings — bypasses Pydantic URL validation | `manual_ingestion_service.py` |
| H7 | Bulk admin actions have no rate limit; partial failures leak raw exception text to clients | `review_queue_service.py`, `admin/review_queue.py` |
| H8 | Wishlist share token makes `is_public=True` as side effect; no expiry; no revocation endpoint | `wishlist_service.py` |
| H9 | Image upload: no decompression-bomb guard; output format derived from `img.format` not magic bytes | `s3_client.py` |
| H10 | Rate-limit key uses load-balancer IP; `request.state.user_id` never set; IP spoofing via XFF header | `rate_limit.py` |
| H11 | CSRF absent — when refresh token cookie is added, all state-changing endpoints become CSRF-able | `main.py` |

---

## Performance Findings

### Summary: 22 findings (6 HIGH, 9 MEDIUM, 4 LOW)

### HIGH

| # | Finding | Location |
|---|---------|----------|
| P1 | OpenAI `extract_gift_filters` + `embed_one` called serially on AI search — +500-1000ms | `search_service.py` |
| P2 | Per-request `view_count` UPDATE causes row-lock contention on popular items | `item_service.py`, `items.py` |
| P3 | IVFFlat `lists=100` + `probes=1` (default) gives ~10% recall at 1M rows; HNSW preferred | migration `001` |
| P4 | Bulk approve/reject loops 250 DB round-trips for 50 items; should use single IN-clause UPDATE | `review_queue_service.py` |
| P5 | Dead code in `upsert_from_scrape` + extra `get_by_id` round-trip per upserted item | `items.py` |
| P6 | Taxonomy/tag data fetched from DB on every discovery page load with no Redis cache | `items.py`, `tags.py` |

---

## Action Items (Critical/High — must address before delivery)

### Security — CRITICAL (fix immediately)
- [ ] **C1**: Move refresh tokens to httpOnly cookie (`backend/app/api/v1/auth.py` + `frontend/src/lib/api/client.ts` + `frontend/src/lib/hooks/useAuth.ts`)
- [ ] **C2**: Add `ALLOWED_TASKS` allowlist in `cron_scheduler_service.py`; use `celery_app.tasks.get()` instead of `importlib.import_module`
- [ ] **C3**: Add `safe_fetch()` wrapper in adapters with scheme allowlist + private IP CIDR deny list (ipaddress module)
- [ ] **C4**: Add startup guard in `config.py` — refuse to boot in production with weak `JWT_SECRET`; remove placeholder from `docker-compose.yml`

### Security — HIGH (fix before launch)
- [ ] **H3**: Validate URL scheme (`http/https` only) in scraper pipeline before persisting `product_url`; add `safeUrl()` helper in frontend
- [ ] **H4**: Add `SecurityHeadersMiddleware` in `main.py` with CSP, HSTS, X-Content-Type-Options, X-Frame-Options
- [ ] **H5**: Replace `item_patch: dict[str, Any]` with typed `ItemApprovalPatch` Pydantic model in `review_queue.py`
- [ ] **H6**: Run `validate_image_url()` on every CSV row's image_url and product_url
- [ ] **H7**: Add `@limiter.limit("10/minute")` on bulk approve/reject; sanitize exception text in BulkActionFailure
- [ ] **H9**: Add `Image.MAX_IMAGE_PIXELS = 24_000_000` guard; derive output format from magic-byte detection, not `img.format`
- [ ] **H10**: Add ProxyHeadersMiddleware; fix `_key_func` to use `request.state.user_id` for authenticated requests

### Performance — HIGH (fix before launch)
- [ ] **P1**: Parallelize OpenAI calls in `ai_natural_language_search` with `asyncio.gather`
- [ ] **P2**: Move counter increments off request path — accumulate in Redis, flush via Celery beat
- [ ] **P3**: Migrate IVFFlat to HNSW in a new Alembic migration
- [ ] **P4**: Replace loop in `bulk_approve`/`bulk_reject` with single `UPDATE ... WHERE id IN (...)`
- [ ] **P6**: Cache taxonomy in Redis with 1-hour TTL; invalidate on taxonomy mutations
