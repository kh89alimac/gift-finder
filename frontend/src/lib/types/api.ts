// ── Tag types ──────────────────────────────────────────────────────────────
export type TagType = 'occasion' | 'interest' | 'recipient' | 'price' | 'theme' | 'other';

export interface TagSlim {
  id: string;
  name: string;
  slug: string;
  type: TagType;
}

export interface Tag extends TagSlim {
  description: string | null;
  itemCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface TagTypeRecord {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  tags: TagSlim[];
  createdAt: string;
  updatedAt: string;
}

// ── Item types ─────────────────────────────────────────────────────────────
export type ItemStatus = 'pending' | 'approved' | 'rejected' | 'archived';
export type ItemSource = 'scraper' | 'instagram' | 'manual' | 'csv';

export interface ItemSummary {
  id: string;
  title: string;
  price: number;
  currency: string;
  imageUrl: string | null;
  thumbnailUrl: string | null;
  retailer: string;
  affiliateUrl: string;
  tags: TagSlim[];
  status: ItemStatus;
  source: ItemSource;
  publishedAt: string | null;
  createdAt: string;
}

export interface Item extends ItemSummary {
  description: string | null;
  originalUrl: string;
  averageRating: number | null;
  reviewCount: number;
}

export interface ItemDetail extends Item {
  similarItems: ItemSummary[];
  metaDescription: string | null;
  brand: string | null;
  sku: string | null;
  inStock: boolean;
  updatedAt: string;
}

// ── Recipient profile ──────────────────────────────────────────────────────
export interface RecipientProfile {
  ageMin: number | null;
  ageMax: number | null;
  relationship: string | null;
  gender: string | null;
  interests: string[];
  occasions: string[];
  budgetMin: number | null;
  budgetMax: number | null;
}

// ── Pagination ─────────────────────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface CursorPage<T> {
  items: T[];
  nextCursor: string | null;
  hasMore: boolean;
  total: number | null;
}

// ── Auth ───────────────────────────────────────────────────────────────────
export interface User {
  id: string;
  email: string;
  displayName: string | null;
  role: 'user' | 'admin';
  createdAt: string;
}

// The refresh token is stored in an httpOnly cookie set by the API. The
// browser sends it automatically with `withCredentials: true`; client code
// never sees the value.
export interface AuthTokens {
  accessToken: string;
  tokenType: 'bearer';
  expiresIn: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  displayName?: string;
}

// ── Wishlist ───────────────────────────────────────────────────────────────
export interface WishlistItem {
  id: string;
  itemId: string;
  item: ItemSummary;
  addedAt: string;
  note: string | null;
  priority: number;
}

export interface Wishlist {
  id: string;
  userId: string;
  name: string;
  description: string | null;
  isPublic: boolean;
  shareToken: string | null;
  itemCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface WishlistDetail extends Wishlist {
  items: WishlistItem[];
}

export interface CreateWishlistRequest {
  name: string;
  description?: string;
  isPublic?: boolean;
}

export interface UpdateWishlistRequest {
  name?: string;
  description?: string;
  isPublic?: boolean;
}

// ── Search ─────────────────────────────────────────────────────────────────
export interface SearchResult {
  item: ItemSummary;
  score: number;
  explanation: string | null;
}

export interface AISearchResponse {
  query: string;
  interpretation: string;
  profile: RecipientProfile;
  results: SearchResult[];
  suggestions: string[];
}

// ── Admin – Review queue ───────────────────────────────────────────────────
export interface ReviewQueueItem {
  id: string;
  item: Item;
  queuedAt: string;
  reviewedAt: string | null;
  reviewedBy: string | null;
  status: 'pending' | 'approved' | 'rejected';
  rejectionReason: string | null;
  source: ItemSource;
  confidence: number | null;
  flags: string[];
}

export interface ApproveItemPatch {
  title?: string;
  description?: string;
  price?: number;
  tags?: string[];
}

// ── Admin – Scraper ────────────────────────────────────────────────────────
export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface ScraperJob {
  id: string;
  siteId: string;
  siteName: string;
  status: JobStatus;
  itemsFound: number;
  itemsAdded: number;
  itemsUpdated: number;
  errors: string[];
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
  triggeredBy: 'cron' | 'manual';
}

export interface ScraperSite {
  id: string;
  name: string;
  baseUrl: string;
  isActive: boolean;
  lastScrapedAt: string | null;
}

// ── Admin – Instagram queue ────────────────────────────────────────────────
export type InstagramTargetType = 'account' | 'hashtag';

export interface InstagramQueueItem {
  id: string;
  target: string;
  targetType: InstagramTargetType;
  status: JobStatus;
  postsProcessed: number;
  itemsExtracted: number;
  createdAt: string;
  completedAt: string | null;
}

// ── Admin – Cron ───────────────────────────────────────────────────────────
export interface CronSchedule {
  id: string;
  name: string;
  expression: string;
  taskType: string;
  taskParams: Record<string, unknown>;
  isActive: boolean;
  lastRunAt: string | null;
  nextRunAt: string | null;
  lastJobId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface CreateCronScheduleRequest {
  name: string;
  expression: string;
  taskType: string;
  taskParams?: Record<string, unknown>;
  isActive?: boolean;
}

export interface UpdateCronScheduleRequest {
  name?: string;
  expression?: string;
  taskParams?: Record<string, unknown>;
  isActive?: boolean;
}

// ── Filters ────────────────────────────────────────────────────────────────
export type SortOption = 'relevance' | 'price_asc' | 'price_desc' | 'newest' | 'popular';

export interface ItemFilters {
  ageMin?: number | null;
  ageMax?: number | null;
  relationship?: string | null;
  occasions?: string[];
  interests?: string[];
  budgetMin?: number | null;
  budgetMax?: number | null;
  sort?: SortOption;
  cursor?: string | null;
  pageSize?: number;
}
