# Gift Finder API Reference

Base URL: `/api/v1`

All requests that mutate state or access private data require an `Authorization: Bearer <access_token>` header unless noted otherwise.

---

## Common Patterns

### Authentication header

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Access tokens expire after 15 minutes. Obtain a fresh one by calling `POST /auth/refresh` — the refresh token is automatically read from the `refresh_token` httpOnly cookie set at login.

### Error response format

Every non-2xx response uses the same envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "Item not found",
    "details": { "item_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6" },
    "request_id": "req_01HX8A..."
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Machine-readable error code (e.g. `validation_error`, `unauthorized`, `not_found`) |
| `message` | string | Human-readable explanation |
| `details` | object | Optional structured context (field errors, constraint names, etc.) |
| `request_id` | string | Server-generated ID that correlates this response to a backend log line |

### Cursor pagination

The discovery feed (`GET /items`) and search results use cursor-based pagination.

```
GET /api/v1/items?page_size=24
```

Response:

```json
{
  "items": [ ... ],
  "next_cursor": "eyJwdWJsaXNoZWRfYXQiOiIyMDI2LTA0LTI5VDE..."
}
```

- `next_cursor` is an opaque base64 string. Pass it as `?cursor=<value>` on the next request to fetch the next page.
- When `next_cursor` is `null`, you are on the last page.
- There is no total count in cursor responses. Issue a separate `COUNT` query via the admin API if you need one.

```
GET /api/v1/items?cursor=eyJwdWJsaXNoZWRfYXQiOiIyMDI2LTA0LTI5VDE...&page_size=24
```

### Rate limits

Auth endpoints are rate-limited per IP (limits shown per endpoint below). All other endpoints share a global 120 req/min per IP ceiling enforced by slowapi.

---

## Auth — `/api/v1/auth`

### POST /auth/register

Create a new user account. Rate-limited to **5 requests/minute** per IP.

**Request**

```json
{
  "email": "alice@example.com",
  "password": "S3cur3P@ss",
  "display_name": "Alice"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `email` | string | yes | Valid email, max 320 chars |
| `password` | string | yes | 8–128 chars, must contain mixed case and digits |
| `display_name` | string | no | max 100 chars |

**Response** `201 Created`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

The `refresh_token` is set as an httpOnly `SameSite=Lax` cookie scoped to `/api/v1/auth`. It is never included in the JSON body.

---

### POST /auth/login

Exchange email and password for an access token. Rate-limited to **10 requests/minute** per IP.

**Request**

```json
{
  "email": "alice@example.com",
  "password": "S3cur3P@ss"
}
```

**Response** `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

---

### POST /auth/refresh

Rotate the refresh cookie and mint a new access token. The request must include the `refresh_token` cookie (sent automatically by the browser). Rate-limited to **30 requests/minute** per IP.

No request body required.

**Response** `200 OK` — same shape as login. The `refresh_token` cookie is replaced with a new one (token family rotation).

---

### POST /auth/logout

Revoke the refresh cookie token and delete the cookie. No auth header required.

**Response** `204 No Content`

---

### GET /auth/me

Return the currently authenticated user.

**Response** `200 OK`

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "alice@example.com",
  "role": "user",
  "display_name": "Alice",
  "avatar_url": null,
  "default_currency": "USD",
  "onboarding_done": false,
  "email_verified": false,
  "last_login_at": "2026-04-29T12:00:00Z",
  "created_at": "2026-04-01T09:00:00Z"
}
```

---

## Discovery — `/api/v1/items`

### GET /items

Paginated discovery feed of active items. Authentication optional (unauthenticated requests see the same feed).

**Query parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tag_ids` | int[] | `[]` | Filter by tag IDs. Repeatable: `?tag_ids=1&tag_ids=5` |
| `require_all_tags` | bool | `false` | When `true`, item must carry every supplied tag (AND). Default is OR. |
| `price_min` | decimal | — | Minimum price (inclusive) |
| `price_max` | decimal | — | Maximum price (inclusive) |
| `cursor` | string | — | Opaque cursor for the next page (from `next_cursor` in prior response) |
| `page_size` | int | `24` | Items per page, 1–100 |

**Response** `200 OK`

```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "title": "Leather Travel Wallet",
      "price": "49.99",
      "currency": "USD",
      "image_url": "https://cdn.example.com/wallet.jpg",
      "product_url": "https://shop.example.com/wallet",
      "brand": "Bellroy",
      "retailer": "Nordstrom",
      "source": "scraper",
      "status": "active",
      "tags": [
        { "id": 12, "name": "Travel", "slug": "travel", "tag_type_id": 1 },
        { "id": 7,  "name": "Birthday", "slug": "birthday", "tag_type_id": 2 }
      ],
      "published_at": "2026-04-15T08:00:00Z"
    }
  ],
  "next_cursor": "eyJwdWJsaXNoZWRfYXQiOiIyMDI2LTA0LTE1VDA4OjAwOjAwWiIsImlkIjoiM2ZhODVmNjQifQ"
}
```

**ItemSummary shape**

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | |
| `title` | string | |
| `price` | decimal\|null | |
| `currency` | string | 3-letter ISO 4217 |
| `image_url` | string\|null | |
| `product_url` | string\|null | |
| `brand` | string\|null | |
| `retailer` | string\|null | |
| `source` | enum | `scraper` \| `instagram` \| `manual` \| `csv_import` |
| `status` | enum | `pending_review` \| `active` \| `rejected` \| `archived` |
| `tags` | TagSlim[] | |
| `published_at` | datetime\|null | |

---

### GET /items/{item_id}

Fetch the full detail view for one item.

**Response** `200 OK` — `ItemDetail` shape (superset of `ItemSummary`):

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Leather Travel Wallet",
  "price": "49.99",
  "currency": "USD",
  "image_url": "https://cdn.example.com/wallet.jpg",
  "product_url": "https://shop.example.com/wallet",
  "brand": "Bellroy",
  "retailer": "Nordstrom",
  "source": "scraper",
  "status": "active",
  "tags": [ ... ],
  "published_at": "2026-04-15T08:00:00Z",
  "description": "A full-grain leather travel wallet with RFID blocking.",
  "source_site_id": 3,
  "source_external_id": "B08XYZ1234",
  "source_url": "https://shop.example.com/wallet",
  "view_count": 412,
  "save_count": 38,
  "click_count": 94,
  "created_at": "2026-04-10T07:30:00Z",
  "updated_at": "2026-04-29T14:22:11Z"
}
```

---

### POST /items/{item_id}/interactions

Record a user interaction signal for recommendations. Requires authentication.

**Request**

```json
{ "interaction_type": "save" }
```

Valid values: `view` | `click` | `save` | `remove` | `share` | `purchase` | `dismiss`

**Response** `204 No Content`

---

### GET /items/categories

Return all active tags of type `category`.

**Response** `200 OK` — array of `TagOut`:

```json
[
  {
    "id": 1,
    "name": "Electronics",
    "slug": "electronics",
    "tag_type_id": 5,
    "parent_tag_id": null,
    "sort_order": 0,
    "is_active": true,
    "tag_metadata": {}
  }
]
```

---

### GET /items/occasions

Return all active tags of type `occasion`.

**Response** `200 OK` — same shape as `/categories`.

---

## Search — `/api/v1/search`

### GET /search

Quick keyword or vector search. Authentication optional.

**Query parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | required | Search query, 1–300 chars |
| `mode` | string | `text` | `text` (PostgreSQL tsvector) or `vector` (pgvector ANN) |
| `limit` | int | `24` | Max results, 1–50 |

**Response** `200 OK` — array of `ItemSummary` (no pagination cursor; results are sorted by relevance score).

---

### POST /search/ai

Natural-language gift search powered by OpenAI function calling + hybrid pgvector/full-text retrieval. Authentication optional.

**Request**

```json
{
  "query": "find a gift for a 30-year-old who loves hiking under $100",
  "profile": {
    "age_range": "25-34",
    "relationship": "friend",
    "interest_tag_ids": [14, 22],
    "occasion_tag_ids": [3],
    "budget_min": null,
    "budget_max": "100.00"
  },
  "limit": 24
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | Natural language gift query, 2–500 chars |
| `profile` | RecipientProfile | no | Optional recipient context to bias results |
| `limit` | int | no | 1–50, default 24 |

**RecipientProfile fields**

| Field | Type | Description |
|-------|------|-------------|
| `age_range` | string\|null | Free-form, e.g. `"25-34"` |
| `relationship` | string\|null | e.g. `"spouse"`, `"colleague"`, `"parent"` |
| `interest_tag_ids` | int[] | Up to 20 interest tag IDs |
| `occasion_tag_ids` | int[] | Up to 10 occasion tag IDs |
| `budget_min` | decimal\|null | |
| `budget_max` | decimal\|null | |

**Response** `200 OK`

```json
{
  "items": [ ... ],
  "extracted": {
    "interest_keywords": ["hiking", "outdoor", "trail"],
    "occasion_keywords": [],
    "recipient_keywords": ["30-year-old", "friend"],
    "price_min": null,
    "price_max": "100.00"
  },
  "mode": "hybrid"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `items` | ItemSummary[] | Ranked results |
| `extracted` | ExtractedFilters | Filters the LLM extracted from the query — display in UI so users can confirm or correct the interpretation |
| `mode` | string | `vector` \| `hybrid` \| `fulltext` — the retrieval strategy used |

---

## Wishlists — `/api/v1/wishlists`

All wishlist endpoints require authentication except viewing a shared wishlist by token.

### GET /wishlists

List all wishlists belonging to the authenticated user.

**Response** `200 OK` — array of `WishlistSummary`:

```json
[
  {
    "id": "a1b2c3d4-...",
    "user_id": "3fa85f64-...",
    "name": "Birthday Ideas for Mom",
    "description": "Under $75",
    "is_public": false,
    "item_count": 5,
    "created_at": "2026-03-01T10:00:00Z",
    "updated_at": "2026-04-20T15:30:00Z"
  }
]
```

---

### POST /wishlists

Create a new wishlist.

**Request**

```json
{
  "name": "Birthday Ideas for Mom",
  "description": "Under $75",
  "is_public": false
}
```

**Response** `201 Created` — `WishlistDetail` (see below).

---

### GET /wishlists/{wishlist_id}

Get a wishlist and its items. Private wishlists require authentication and ownership. Public wishlists can be read anonymously.

**Response** `200 OK` — `WishlistDetail`:

```json
{
  "id": "a1b2c3d4-...",
  "user_id": "3fa85f64-...",
  "name": "Birthday Ideas for Mom",
  "description": "Under $75",
  "is_public": false,
  "item_count": 2,
  "share_token": null,
  "share_url": null,
  "created_at": "2026-03-01T10:00:00Z",
  "updated_at": "2026-04-20T15:30:00Z",
  "items": [
    {
      "id": "wi-uuid-...",
      "wishlist_id": "a1b2c3d4-...",
      "item_id": "3fa85f64-...",
      "priority": "high",
      "notes": "She mentioned wanting this",
      "is_purchased": false,
      "added_at": "2026-04-20T15:30:00Z",
      "item": { ... }
    }
  ]
}
```

---

### PATCH /wishlists/{wishlist_id}

Update wishlist metadata. Must be the owner.

**Request** (all fields optional)

```json
{
  "name": "Updated Name",
  "description": "New description",
  "is_public": true
}
```

**Response** `200 OK` — updated `WishlistDetail`.

---

### DELETE /wishlists/{wishlist_id}

Delete the wishlist and all its items. Must be the owner.

**Response** `204 No Content`

---

### POST /wishlists/{wishlist_id}/items

Add an item to the wishlist.

**Request**

```json
{
  "item_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "priority": "high",
  "notes": "Size M"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `item_id` | UUID | required | |
| `priority` | string | `"normal"` | max 20 chars |
| `notes` | string\|null | null | max 2000 chars |

**Response** `201 Created` — `WishlistItemOut`.

---

### DELETE /wishlists/{wishlist_id}/items/{item_id}

Remove an item from the wishlist. Must be the owner.

**Response** `204 No Content`

---

### POST /wishlists/{wishlist_id}/share

Generate or regenerate a share token for the wishlist.

**Response** `200 OK`

```json
{
  "share_token": "abc123def456ghi789jkl012",
  "share_url": "https://giftfinder.app/wishlists/shared/abc123def456ghi789jkl012"
}
```

Anyone with this URL can view the wishlist without logging in.

---

### GET /wishlists/shared/{token}

View a wishlist by share token. No authentication required.

**Response** `200 OK` — `WishlistDetail` (same shape as `GET /wishlists/{wishlist_id}`).

---

## Recommendations — `/api/v1/recommendations`

### GET /recommendations

Personalized recommendations for authenticated users; anonymous users receive a trending cold-start feed.

**Query parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page_size` | int | `24` | 1–50 |

**Response** `200 OK`

```json
{
  "items": [
    {
      "item": { ... },
      "score": 0.92,
      "reason": "Based on your interest in Travel"
    }
  ],
  "is_personalized": true,
  "generated_at": "2026-04-29T14:00:00Z"
}
```

`is_personalized` is `false` for anonymous users or users without enough interaction history (cold start).

---

### POST /recommendations/refresh

Force-recompute the authenticated user's recommendations. Useful after updating interests.

**Response** `200 OK` — same shape as `GET /recommendations`.

---

### POST /recommendations/profile

Get recommendations biased toward an explicit recipient profile (gift-giver flow). Authentication optional.

**Request** — `RecipientProfile` object (same schema as AI search profile above).

**Query parameters** — `page_size` (default 24, max 50).

**Response** `200 OK` — same shape as `GET /recommendations`.

---

### GET /recommendations/similar/{item_id}

Fetch items similar to the given item using vector similarity.

**Query parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n` | int | `5` | Number of similar items, 1–20 |

**Response** `200 OK` — array of `ItemSummary`.

---

## Admin — Review Queue — `/api/v1/admin/review-queue`

All admin endpoints require a valid access token for a user with `role = "admin"`.

### GET /admin/review-queue

List items in the moderation queue (offset-paginated).

**Query parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | enum | — | Filter by source: `scraper` \| `instagram` \| `manual` \| `csv_import` |
| `assigned_to` | UUID | — | Filter by reviewer UUID |
| `page` | int | `1` | |
| `page_size` | int | `50` | 1–200 |

**Response** `200 OK`

```json
{
  "items": [ ... ],
  "meta": {
    "page": 1,
    "page_size": 50,
    "total": 143,
    "total_pages": 3
  }
}
```

---

### GET /admin/review-queue/{queue_id}

Fetch a single queue entry.

**Response** `200 OK` — `ReviewQueueItem`.

---

### POST /admin/review-queue/{queue_id}/approve

Approve an item and publish it. Optionally patch fields before publishing.

**Request**

```json
{
  "item_patch": {
    "title": "Corrected Title",
    "tag_ids": [1, 5, 9]
  }
}
```

`item_patch` is optional; all its fields follow the same constraints as `ItemManualUpdate`.

**Response** `200 OK` — `ItemDetail`.

---

### POST /admin/review-queue/{queue_id}/reject

Reject a queue item with an optional reason.

**Request**

```json
{ "reason": "Duplicate listing" }
```

**Response** `200 OK` — `ItemDetail`.

---

### POST /admin/review-queue/bulk/approve

Approve multiple items in one call. Rate-limited to **10 requests/minute**.

**Request**

```json
{
  "queue_ids": [
    "uuid-1", "uuid-2", "uuid-3"
  ]
}
```

**Response** `200 OK`

```json
{
  "successes": 2,
  "failures": [
    { "id": "uuid-3", "reason": "Item already reviewed" }
  ]
}
```

---

### POST /admin/review-queue/bulk/reject

Reject multiple items. Rate-limited to **10 requests/minute**.

**Request**

```json
{
  "queue_ids": ["uuid-1", "uuid-2"],
  "reason": "Off-topic products"
}
```

**Response** `200 OK` — same `BulkActionResult` shape.

---

### Keyboard shortcuts (review queue UI)

| Key | Action |
|-----|--------|
| `A` | Approve current item |
| `R` | Reject current item |
| `S` | Skip (move to next without decision) |
| `ArrowLeft` / `ArrowRight` | Previous / next item |
| `Space` | Expand item detail panel |
| `Ctrl+A` | Select all visible items |

---

## Admin — Taxonomy — `/api/v1/admin/taxonomy`

### Tag Types

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/taxonomy/tag-types` | List all tag types with their child tags |
| `POST` | `/admin/taxonomy/tag-types` | Create a tag type |
| `PATCH` | `/admin/taxonomy/tag-types/{type_id}` | Update a tag type |
| `DELETE` | `/admin/taxonomy/tag-types/{type_id}` | Delete a tag type (blocked if tags exist) |

**POST /admin/taxonomy/tag-types request**

```json
{
  "name": "mood",
  "description": "Emotional tone of the gift",
  "is_filterable": true,
  "sort_order": 70
}
```

**TagTypeOut response shape**

```json
{
  "id": 7,
  "name": "mood",
  "description": "Emotional tone of the gift",
  "is_filterable": true,
  "sort_order": 70,
  "tags": []
}
```

---

### Tags

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/admin/taxonomy/tags` | Create a tag |
| `PATCH` | `/admin/taxonomy/tags/{tag_id}` | Update a tag |
| `DELETE` | `/admin/taxonomy/tags/{tag_id}` | Delete a tag |

**POST /admin/taxonomy/tags request**

```json
{
  "tag_type_id": 1,
  "name": "Photography",
  "slug": "photography",
  "parent_tag_id": null,
  "sort_order": 0,
  "is_active": true,
  "tag_metadata": {}
}
```

Slug must match `^[a-z0-9]+(?:-[a-z0-9]+)*$`. Slugs are unique within a tag type.

---

### POST /admin/taxonomy/tags/merge

Merge one tag into another. All `item_tags` rows pointing to `source_tag_id` are repointed to `target_tag_id`, then `source_tag_id` is deleted.

**Use case**: two admins independently created `"Photography"` (id=14) and `"photo"` (id=23) — merge 23 into 14 to consolidate.

**Request**

```json
{
  "source_tag_id": 23,
  "target_tag_id": 14
}
```

**Response** `200 OK`

```json
{ "moved_item_tags": 47 }
```

---

## Admin — Ingestion — `/api/v1/admin/ingestion`

### Scraper

#### POST /admin/ingestion/scraper/trigger

Enqueue a scrape job for a site. Rate-limited to **30 requests/minute**. Returns `202 Accepted`.

**Request**

```json
{
  "site_id": 3,
  "priority": 5
}
```

`priority` is 1–10 (higher = more urgent). Default is 5.

**Response** `202 Accepted` — `ScraperJobOut`:

```json
{
  "id": "job-uuid-...",
  "site_id": 3,
  "schedule_id": null,
  "status": "queued",
  "priority": 5,
  "items_found": 0,
  "items_created": 0,
  "items_updated": 0,
  "items_skipped": 0,
  "error_message": null,
  "retry_count": 0,
  "started_at": null,
  "completed_at": null,
  "created_at": "2026-04-29T14:05:00Z",
  "updated_at": "2026-04-29T14:05:00Z"
}
```

#### GET /admin/ingestion/scraper/jobs

List recent scraper jobs (most recent first).

**Query parameters**: `limit` (default 50, max 200).

**Response** `200 OK` — array of `ScraperJobOut`. Poll this endpoint to track job progress; a job moves from `queued` → `running` → `completed` or `failed`.

---

### Instagram

#### POST /admin/ingestion/instagram/trigger

Dispatch a Celery task to fetch posts from an Instagram account or hashtag. Rate-limited to **10 requests/minute**.

**Request**

```json
{
  "target": "willowgiftco",
  "target_type": "user",
  "limit": 25
}
```

`target_type` is `"user"` or `"hashtag"`. `limit` is 1–100, default 25.

**Response** `202 Accepted`

```json
{ "task_id": "celery-task-uuid-..." }
```

---

#### GET /admin/ingestion/instagram/queue

List pending Instagram posts awaiting review.

**Query parameters**: `limit` (default 50, max 200).

**Response** `200 OK` — array of `InstagramQueueItem`.

---

#### POST /admin/ingestion/instagram/queue/{queue_id}/approve

Promote an Instagram post to an active `items` row.

**Response** `200 OK` — updated `InstagramQueueItem` (with `status: "approved"` and `promoted_item_id` set).

---

#### POST /admin/ingestion/instagram/queue/{queue_id}/reject

Reject an Instagram post with an optional reason query param `?reason=off-topic`.

**Response** `200 OK` — updated `InstagramQueueItem`.

---

### Manual entry

#### POST /admin/ingestion/manual/items

Create an item manually.

**Request**

```json
{
  "title": "Handmade Soy Candle Set",
  "description": "Three-piece soy candle set with botanical scents.",
  "price": "38.00",
  "currency": "USD",
  "image_url": "https://cdn.example.com/candle.jpg",
  "product_url": "https://shop.example.com/candle",
  "brand": "WickCraft",
  "retailer": "Etsy",
  "tag_ids": [3, 7, 15],
  "publish": true
}
```

Setting `publish: true` creates the item with `status=active`; `false` (default) creates it as `pending_review`.

**Response** `201 Created` — `ItemDetail`.

---

#### PATCH /admin/ingestion/manual/items/{item_id}

Update a manually-created or any item. All fields optional.

**Request** — same fields as POST but all optional. Can also update `status` directly.

**Response** `200 OK` — `ItemDetail`.

---

#### POST /admin/ingestion/manual/items/{item_id}/image

Upload an image for an item. `multipart/form-data` with a single `file` field.

**Response** `200 OK`

```json
{
  "item_id": "3fa85f64-...",
  "image_url": "https://giftfinder-images.s3.us-east-1.amazonaws.com/items/3fa85f64-...-original.jpg",
  "image_s3_key": "items/3fa85f64-...-original.jpg"
}
```

---

#### POST /admin/ingestion/manual/csv-import

Bulk-import items from a CSV file. `multipart/form-data` with a single `file` field.

**CSV format specification**

Required columns (header row is mandatory):

| Column | Type | Notes |
|--------|------|-------|
| `title` | string | Max 500 chars, required |
| `price` | decimal | Optional, omit or leave blank |
| `currency` | string | 3-letter ISO code, default `USD` |
| `product_url` | string | Optional |
| `image_url` | string | Optional |
| `brand` | string | Optional, max 200 chars |
| `retailer` | string | Optional, max 200 chars |
| `description` | string | Optional |
| `tag_slugs` | string | Optional, pipe-separated slugs: `travel\|birthday` |

**Example rows**

```csv
title,price,currency,product_url,image_url,brand,retailer,description,tag_slugs
Leather Journal,24.99,USD,https://shop.com/journal,https://cdn.com/j.jpg,Leuchtturm,Amazon,A5 dot-grid notebook,writing|stationery
Hiking Socks,18.00,USD,https://shop.com/socks,,Darn Tough,REI,,hiking|outdoor
```

Each row is processed in its own savepoint — a row failure does not roll back the entire import.

**Response** `200 OK`

```json
{
  "total_rows": 50,
  "inserted": 47,
  "updated": 1,
  "skipped": 1,
  "errors": [
    {
      "row_number": 23,
      "errors": ["title: field required", "price: value is not a valid decimal"]
    }
  ]
}
```

---

## Admin — Cron — `/api/v1/admin/cron`

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/cron` | List all schedules |
| `POST` | `/admin/cron` | Create a schedule |
| `GET` | `/admin/cron/{schedule_id}` | Get a schedule |
| `PATCH` | `/admin/cron/{schedule_id}` | Update a schedule |
| `DELETE` | `/admin/cron/{schedule_id}` | Delete a schedule |
| `POST` | `/admin/cron/{schedule_id}/enable` | Enable (re-activate) a schedule |
| `POST` | `/admin/cron/{schedule_id}/disable` | Disable a schedule without deleting it |
| `POST` | `/admin/cron/{schedule_id}/trigger` | Run the schedule immediately (on-demand) |

### POST /admin/cron request

```json
{
  "name": "Scrape Amazon daily",
  "cron_expr": "0 2 * * *",
  "task_name": "app.workers.tasks.scrape.scrape_site_task",
  "task_kwargs": { "site_id": 1 },
  "is_active": true
}
```

`cron_expr` must be a standard 5- or 6-field cron expression.

### CronScheduleOut response shape

```json
{
  "id": 4,
  "name": "Scrape Amazon daily",
  "cron_expr": "0 2 * * *",
  "task_name": "app.workers.tasks.scrape.scrape_site_task",
  "task_kwargs": { "site_id": 1 },
  "is_active": true,
  "last_run_at": "2026-04-28T02:00:05Z",
  "next_run_at": "2026-04-29T02:00:00Z",
  "created_at": "2026-04-01T09:00:00Z",
  "updated_at": "2026-04-28T02:00:05Z"
}
```

### POST /admin/cron/{schedule_id}/trigger response

```json
{ "task_id": "celery-task-uuid-..." }
```
