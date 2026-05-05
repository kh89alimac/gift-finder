# Gift Finder — Handoff Summary

## What was built

Gift Finder is a web application where users discover personalized gift ideas. Users supply a recipient profile (age range, relationship, interests, occasion, budget) and browse or search a curated product catalog. Items are tagged across six dimensions (interest, occasion, recipient, price_band, category, style).

### Feature summary

| Area | What is included |
|------|-----------------|
| Discovery | Paginated gift feed with tag + price filters, cursor pagination |
| Search | Full-text search (PostgreSQL tsvector) + vector search (pgvector ANN) + AI natural-language search (OpenAI function calling) |
| Recommendations | Personalized recs from pre-computed tag affinity signals; cold-start trending feed for anonymous users; "similar items" via vector similarity |
| Wishlists | Full CRUD, add/remove items, shareable read-only links via share tokens |
| Auth | JWT (15-min access token + 7-day refresh cookie), token family rotation, Redis JTI revocation, role-based access (user / admin) |
| Admin — Review queue | Moderation UI with keyboard shortcuts, bulk approve/reject |
| Admin — Taxonomy | Tag types and tags CRUD, tag merge |
| Admin — Ingestion | Web scraper trigger + job status polling; Instagram Graph API trigger + review queue; manual item entry; bulk CSV import; image upload to S3 |
| Admin — Cron | Celery-redbeat schedule CRUD, on-demand trigger |

### Scope boundaries (explicitly not built)

- No checkout or payment flow — items link out to the retailer's product page
- No social features (following, commenting, shared feeds)
- No email verification flow (the `email_verified` column exists; the logic to send and verify the link is not wired up)
- No native mobile app — the frontend is mobile-responsive web only
- No i18n/multi-language support

---

## How to get running locally

### Prerequisites

- Docker Desktop (or Docker Engine + Compose v2)
- Node.js 20
- Python 3.12
- `pip` or `uv` (either works)

### Steps

**1. Configure environment**

```bash
cp .env.example .env
```

Open `.env` and fill in the required values:

| Variable | What to put |
|----------|-------------|
| `SECRET_KEY` | Any 32+ char random string: `openssl rand -hex 32` |
| `JWT_SECRET` | Any 32+ char random string: `openssl rand -hex 32` |
| `OPENAI_API_KEY` | Your OpenAI API key (required for AI search and auto-categorization) |
| `AWS_ACCESS_KEY_ID` | AWS key with S3 put/get on the target bucket (required for image upload) |
| `AWS_SECRET_ACCESS_KEY` | Corresponding secret |
| `S3_BUCKET` | Your S3 bucket name |
| `INSTAGRAM_ACCESS_TOKEN` | Instagram Graph API long-lived token (only needed for IG ingestion) |
| `CORS_ORIGINS` | `http://localhost:3000` for local dev |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` |

Leave `DATABASE_URL` and `REDIS_URL` commented out for local development — the docker compose service names resolve automatically.

**2. Start PostgreSQL and Redis**

```bash
docker compose up -d postgres redis
```

**3. Install backend and run migrations**

```bash
cd backend
pip install -e .
alembic upgrade head
```

**4. Start the API server**

```bash
uvicorn app.main:app --reload
```

The API is now available at http://localhost:8000. Interactive docs are at http://localhost:8000/api/v1/docs (dev only — Swagger UI is disabled in production).

**5. (Optional) Start a Celery worker**

Background jobs (scraping, embedding, recommendations) require a worker:

```bash
# From the backend directory
celery -A app.workers.celery_app worker --loglevel=info -Q default,scraping,embedding,recommendations
```

**6. Install and start the frontend**

```bash
cd frontend
npm install
npm run dev
```

The app is now available at http://localhost:3000.

---

## How to test

### Backend tests

```bash
cd backend
pytest tests/ -v
```

The test suite uses an isolated test database; see `backend/tests/conftest.py` for the fixture setup. The database URL for tests is configured via `TEST_DATABASE_URL` in the environment (falls back to an in-memory SQLite equivalent via override in conftest).

### API exploration (dev only)

The FastAPI auto-generated docs are available at:

```
http://localhost:8000/api/v1/docs     (Swagger UI)
http://localhost:8000/api/v1/redoc   (ReDoc)
```

Both are disabled when `APP_ENV=production`.

---

## How to add a new scraper site

1. **Create the adapter file**

   ```bash
   touch backend/app/adapters/my_site.py
   ```

   Implement `BaseScrapeAdapter` from `backend/app/adapters/base.py`:

   ```python
   from app.adapters.base import BaseScrapeAdapter, ScrapeResult
   from collections.abc import AsyncIterator

   class MySiteAdapter(BaseScrapeAdapter):
       name = "my_site"

       def scrape(self) -> AsyncIterator[ScrapeResult]:
           # yield ScrapeResult(...) for each product found
           ...

       async def health_check(self) -> bool:
           # return True if the site is reachable and parsing correctly
           ...
   ```

   `ScrapeResult.source_external_id` must be a stable identifier for the product (e.g. the retailer's SKU or product path). It is used together with `site_id` to deduplicate items across runs.

2. **Register the adapter**

   Open `backend/app/adapters/registry.py` and add the new adapter to the registry dict:

   ```python
   ADAPTER_REGISTRY: dict[str, type[BaseScrapeAdapter]] = {
       "amazon":       AmazonAdapter,
       "etsy":         EtsyAdapter,
       "generic_html": GenericHtmlAdapter,
       "my_site":      MySiteAdapter,   # add this line
   }
   ```

3. **Create the `scraper_sites` row**

   In the admin panel, go to **Ingestion → Sites** and add a new site:

   | Field | Value |
   |-------|-------|
   | Name | `My Site` |
   | Base URL | `https://www.mysite.com` |
   | Adapter class | `my_site` (must match the key in the registry) |
   | Rate limit (rps) | `1.0` (start conservative) |

   Alternatively, insert directly:

   ```sql
   INSERT INTO scraper_sites (name, base_url, adapter_class, rate_limit_rps)
   VALUES ('My Site', 'https://www.mysite.com', 'my_site', 1.0);
   ```

4. **Trigger a test run**

   Use the admin panel's **Ingestion → Trigger Scraper** form or call the API:

   ```bash
   curl -X POST http://localhost:8000/api/v1/admin/ingestion/scraper/trigger \
     -H "Authorization: Bearer <admin_token>" \
     -H "Content-Type: application/json" \
     -d '{"site_id": <new_site_id>, "priority": 8}'
   ```

   Monitor the job at `GET /api/v1/admin/ingestion/scraper/jobs`.

---

## Known limitations and backlog

### Performance

- **Counter update contention** (`view_count`, `save_count`, `click_count` on `items`): these are direct `UPDATE` increments. Under high concurrent traffic the same row is updated by many workers simultaneously, causing lock contention. The planned fix is Redis `INCR` batching (accumulate in Redis, flush to Postgres every N seconds). Deferred to the first post-launch sprint.
- **`upsert_from_scrape` extra round-trip**: the scraper upsert path makes a `SELECT` before the `INSERT ... ON CONFLICT UPDATE`. This is a minor inefficiency; it can be collapsed to a pure upsert with a RETURNING clause. Deferred.

### Security

The security review in `.full-stack-feature/07-testing.md` identified **11 MEDIUM** and **9 LOW** severity findings. None are critical/high. The key MEDIUM items are:

- Missing `Content-Security-Policy` header (frontend)
- `INSTAGRAM_ACCESS_TOKEN` long-lived token rotation not automated
- S3 bucket policy not restricted to pre-signed URLs (images are public-read)
- Flower monitoring endpoint lacks IP allowlist in default config

Review the full list in `.full-stack-feature/07-testing.md` before going to production. The `PRODUCTION_CHECKLIST.md` in the repo root cross-references these items.

### Missing features (not out of scope, just not yet implemented)

- **Email verification**: the `users.email_verified` column exists and is returned in `GET /auth/me`, but the verification email is never sent and the verify-token endpoint does not exist. Users can register and log in without verifying their email.
- **Admin audit log**: there is no `admin_audit_log` table. Individual field-level changes to items can be traced through `ingestion_log`, but there is no consolidated audit trail of "admin X approved item Y at time T".
- **OAuth login**: the `users.oauth_provider` and `users.oauth_provider_id` columns exist; the OAuth flow is not implemented.

### Not in scope

- i18n / multi-language: there is no implementation and no explicit decision was made to exclude it. The `currency` field per item and `default_currency` per user exist, but prices are stored in a single currency with no conversion. Multi-currency display was not built.
- Mobile-responsive web is implemented; no native iOS/Android app.

---

## Where to find things

| Path | Contents |
|------|---------|
| `.full-stack-feature/` | All planning documents: requirements (01), database design (02), architecture (03), implementation notes (04–06), testing report (07), deployment guide (08) |
| `backend/app/` | FastAPI application root |
| `backend/app/api/v1/` | All route handlers |
| `backend/app/models/` | SQLAlchemy ORM models |
| `backend/app/schemas/` | Pydantic request/response schemas |
| `backend/app/services/` | Business logic layer |
| `backend/app/repositories/` | Database query layer (Unit of Work pattern) |
| `backend/app/workers/` | Celery app definition and tasks |
| `backend/app/adapters/` | Scraper adapter implementations |
| `backend/app/migrations/versions/` | Alembic migration files |
| `frontend/src/app/` | Next.js App Router pages |
| `frontend/src/components/` | React components |
| `frontend/src/lib/api/` | Typed API client functions |
| `frontend/src/lib/hooks/` | TanStack Query hooks |
| `frontend/src/lib/store/` | Zustand stores |
| `RUNBOOK.md` | Deployment and operations playbook (scaling, rollback, log access, on-call runbook) |
| `PRODUCTION_CHECKLIST.md` | Pre-launch checklist |
| `docs/api.md` | API reference (this docs folder) |
| `docs/schema.md` | Database schema reference |
| `docs/architecture-decisions.md` | Architecture decision records |
