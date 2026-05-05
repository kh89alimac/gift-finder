import apiClient from '../client';
import type {
  InstagramQueueItem,
  InstagramTargetType,
  Item,
  ItemSummary,
  PaginatedResponse,
  ScraperJob,
  ScraperSite,
} from '../../types/api';

interface JobFilters {
  status?: string;
  siteId?: string;
  page?: number;
  pageSize?: number;
}

// ── Scraper ────────────────────────────────────────────────────────────────
export async function listSites(): Promise<ScraperSite[]> {
  const response = await apiClient.get<ScraperSite[]>('/admin/ingestion/sites');
  return response.data;
}

export async function triggerScraper(siteId: string): Promise<ScraperJob> {
  const response = await apiClient.post<ScraperJob>(`/admin/ingestion/sites/${siteId}/scrape`);
  return response.data;
}

export async function listJobs(filters: JobFilters = {}): Promise<PaginatedResponse<ScraperJob>> {
  const params: Record<string, unknown> = {};
  if (filters.status) params.status = filters.status;
  if (filters.siteId) params.site_id = filters.siteId;
  if (filters.page) params.page = filters.page;
  if (filters.pageSize) params.page_size = filters.pageSize;

  const response = await apiClient.get<PaginatedResponse<ScraperJob>>('/admin/ingestion/jobs', { params });
  return response.data;
}

export async function getJob(id: string): Promise<ScraperJob> {
  const response = await apiClient.get<ScraperJob>(`/admin/ingestion/jobs/${id}`);
  return response.data;
}

// ── Instagram ──────────────────────────────────────────────────────────────
export async function triggerInstagram(
  target: string,
  type: InstagramTargetType
): Promise<InstagramQueueItem> {
  const response = await apiClient.post<InstagramQueueItem>('/admin/ingestion/instagram', {
    target,
    type,
  });
  return response.data;
}

export async function listInstagramQueue(): Promise<InstagramQueueItem[]> {
  const response = await apiClient.get<InstagramQueueItem[]>('/admin/ingestion/instagram/queue');
  return response.data;
}

// ── CSV Import ─────────────────────────────────────────────────────────────
export async function importCSV(file: File): Promise<{ jobId: string; itemsQueued: number }> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await apiClient.post<{ jobId: string; itemsQueued: number }>(
    '/admin/ingestion/csv',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return response.data;
}

// ── Manual item creation ───────────────────────────────────────────────────
export async function createItem(
  data: Partial<Item> & { title: string; price: number; retailer: string }
): Promise<ItemSummary> {
  const response = await apiClient.post<ItemSummary>('/admin/items', data);
  return response.data;
}

export async function uploadImage(itemId: string, file: File): Promise<{ imageUrl: string }> {
  const formData = new FormData();
  formData.append('image', file);
  const response = await apiClient.post<{ imageUrl: string }>(
    `/admin/items/${itemId}/image`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return response.data;
}

// ── Admin item list ────────────────────────────────────────────────────────
export async function listAdminItems(filters: {
  q?: string;
  status?: string;
  source?: string;
  page?: number;
  pageSize?: number;
} = {}): Promise<PaginatedResponse<ItemSummary>> {
  const params: Record<string, unknown> = {};
  if (filters.q) params.q = filters.q;
  if (filters.status) params.status = filters.status;
  if (filters.source) params.source = filters.source;
  if (filters.page) params.page = filters.page;
  if (filters.pageSize) params.page_size = filters.pageSize;

  const response = await apiClient.get<PaginatedResponse<ItemSummary>>('/admin/items', { params });
  return response.data;
}

export async function updateItemStatus(id: string, status: string): Promise<ItemSummary> {
  const response = await apiClient.patch<ItemSummary>(`/admin/items/${id}`, { status });
  return response.data;
}
