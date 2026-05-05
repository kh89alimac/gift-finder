# Documentation: Gift Finder App

## Files Created

- `docs/api.md` (25 KB) — Complete API reference: all 40+ endpoints with full JSON request/response examples for register/login, AI search (with `interpretation` field), wishlists + share token flow, bulk approve/reject, CSV import format, keyboard shortcuts reference
- `docs/schema.md` (8 KB) — All 15 tables, 6 ENUM types, triggers, HNSW index parameters, seed data, migration notes (including HNSW CONCURRENTLY caveat)
- `docs/architecture-decisions.md` (15 KB) — 5 ADRs: unified items table, pgvector vs. Elasticsearch, Celery+Redis vs. DB queue, cursor pagination, httpOnly cookie token split
- `docs/handoff.md` (10 KB) — Feature summary, local setup (7 steps), test instructions, "how to add a new scraper" walkthrough with code sample, known limitations, where-to-find-things

## Key decisions documented in ADRs

- **ADR-001**: Single `items` table with source+status enums (vs. separate tables per source)
- **ADR-002**: pgvector HNSW (vs. Elasticsearch/Pinecone) — zero extra infra, co-located with relational data
- **ADR-003**: Celery + Redis + celery-redbeat (vs. DB-backed queue like pgqueue)
- **ADR-004**: Cursor pagination on `(published_at DESC, id DESC)` (vs. offset) — O(1) deep pages, shareable URLs
- **ADR-005**: httpOnly cookie for refresh token + in-memory access token (vs. localStorage)

## Known limitations documented

- Counter update contention (view_count) under high traffic — Redis INCR batching in backlog
- 11 MEDIUM + 9 LOW security findings still open (see `.full-stack-feature/07-testing.md`)
- Email verification not wired (column exists, logic not implemented)
- No admin audit log table
- No OAuth provider login
- i18n not implemented
