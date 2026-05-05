import apiClient from './client';
import type { AISearchResponse, ItemFilters, ItemSummary, PaginatedResponse, RecipientProfile } from '../types/api';

export async function textSearch(
  query: string,
  filters: ItemFilters = {}
): Promise<PaginatedResponse<ItemSummary>> {
  const params: Record<string, unknown> = { q: query };

  if (filters.budgetMin != null) params.budget_min = filters.budgetMin;
  if (filters.budgetMax != null) params.budget_max = filters.budgetMax;
  if (filters.occasions?.length) params.occasions = filters.occasions.join(',');
  if (filters.interests?.length) params.interests = filters.interests.join(',');

  const response = await apiClient.get<PaginatedResponse<ItemSummary>>('/search', { params });
  return response.data;
}

export async function aiSearch(
  query: string,
  profile?: Partial<RecipientProfile>
): Promise<AISearchResponse> {
  const response = await apiClient.post<AISearchResponse>('/search/ai', { query, profile });
  return response.data;
}
