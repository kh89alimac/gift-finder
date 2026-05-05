# Frontend Implementation: Gift Finder App

## Files Created (66 total, 60 TypeScript/TSX)

### Config
- `package.json` — Next.js 14, React 18, TypeScript 5, Tailwind 3, Zustand 4, TanStack Query 5, nuqs, Sonner, axios
- `next.config.js` — wildcard image domains, `/api/v1/*` rewrite to `localhost:8000`
- `tailwind.config.ts` — warm gift palette (gift, warm, blush color scales)
- `tsconfig.json`, `postcss.config.js`

### Types (`src/lib/types/api.ts`)
30+ interfaces: Item, ItemSummary, ItemDetail, RecipientProfile, Tag, TagType, Wishlist, WishlistDetail, User, AuthTokens, PaginatedResponse<T>, CursorPage<T>, ReviewQueueItem, ScraperJob, CronSchedule, InstagramQueueItem, AISearchResponse, SearchResult

### API Client (`src/lib/api/`)
10 files:
- `client.ts` — axios with Bearer token injection (lazy store access to avoid circular imports), 401→refresh→retry interceptor with queue draining
- `auth.ts`, `items.ts`, `search.ts`, `wishlists.ts`, `recommendations.ts`
- `admin/queue.ts`, `admin/taxonomy.ts`, `admin/ingestion.ts`, `admin/cron.ts`

### State Stores (`src/lib/store/`)
- `authStore.ts` — user persisted to localStorage only (token in memory), `isAdmin()` helper
- `filterStore.ts` — all discovery filters + `hasActiveFilters()`, `resetFilters()`
- `wishlistStore.ts` — optimistic add/remove with `pendingAdd`/`pendingRemove` Sets
- `adminStore.ts` — bulk selection with `toggleSelect`, `selectAll`, `clearSelection`

### React Query Hooks (`src/lib/hooks/`)
13 files:
- `useDiscovery.ts` — `useInfiniteQuery` keyed on filter store
- `useItemDetail.ts` — parallel item + similar items queries
- `useAISearch.ts` — mutation + local state for last result
- `useWishlists.ts` — CRUD + optimistic add/remove
- `useAuth.ts` — login/register/logout mutations
- `admin/useReviewQueue.ts`, `useTaxonomy.ts`, `useIngestion.ts` (5s polling on active jobs), `useCron.ts`

### Pages (16)
- `/` — Hero + 6 quick-start profile cards + how-it-works
- `/discover` — Filter panel (desktop left, mobile bottom-sheet) + infinite-scroll grid
- `/discover/loading` — skeleton matching grid
- `/item/[id]` — SSR + ItemDetailClient: image, tags, CTA, similar items
- `/search` — AI search: example chips, interpretation display, refinement suggestions
- `/wishlists` — grid with create form
- `/wishlists/[id]` — items table, share token copy, public/private toggle
- `/auth/login`, `/auth/register` — validated forms
- `/admin/layout` — guards with `isAdmin()` redirect, AdminSidebar
- `/admin` — stat cards + quick actions
- `/admin/queue` — keyboard nav (↑↓, A, R, Space, Ctrl+A) + BulkActionBar
- `/admin/taxonomy` — tree tag type list + inline tag CRUD
- `/admin/ingestion` — cron table, scraper triggers, CSV drag-drop, job polling
- `/admin/items` — searchable table with inline status dropdown

### Components (11)
- `gift/GiftCard` — Next.js Image blur placeholder, wishlist heart, hover overlay, tag chips
- `gift/GiftGrid` — 1-4 column responsive grid, IntersectionObserver sentinel
- `gift/TagBadge` — color-coded by tag type, clickable variant
- `discovery/FilterPanel` — relationship, age, occasion, interests, budget + mobile apply button
- `discovery/ActiveFilters` — chips with individual/clear-all removal
- `layout/Header` — sticky, desktop nav, avatar menu, mobile hamburger
- `admin/AdminSidebar` — active-page highlighting
- `admin/ReviewQueueTable` — full keyboard nav, confidence bar, source badges
- `admin/BulkActionBar` — fixed bottom with reject reason modal
- `admin/CronScheduleTable` — inline cron human-readable parser, trigger/enable/disable
- `ui/ErrorBoundary` — class component with retry button

### Utilities
- `format.ts` — `formatPrice` (Intl), relative/absolute dates, `truncate`, `parseCronToHuman`
- `cursor.ts` — base64 cursor encode/decode
- `cn.ts` — clsx + tailwind-merge

## Key design decisions
- Access token in Zustand memory only (not localStorage) — prevents XSS token theft
- Lazy `import()` in axios interceptor avoids circular auth module dependency
- `useInfiniteQuery` polling stops when no active jobs (`refetchInterval: false` when idle)
- Full TypeScript coverage, no `any` types
- Tailwind-only styling
