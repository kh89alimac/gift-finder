import apiClient from './client';
import type { CursorPage, ItemDetail, ItemFilters, ItemSummary, TagTypeRecord } from '../types/api';

export async function listItems(
  filters: ItemFilters = {},
  cursor?: string | null
): Promise<CursorPage<ItemSummary>> {
  const params: Record<string, unknown> = {};

  if (filters.ageMin != null) params.age_min = filters.ageMin;
  if (filters.ageMax != null) params.age_max = filters.ageMax;
  if (filters.relationship) params.relationship = filters.relationship;
  if (filters.occasions?.length) params.occasions = filters.occasions.join(',');
  if (filters.interests?.length) params.interests = filters.interests.join(',');
  if (filters.budgetMin != null) params.price_min = filters.budgetMin;
  if (filters.budgetMax != null) params.price_max = filters.budgetMax;
  if (filters.sort && filters.sort !== 'relevance') params.sort = filters.sort;
  if (cursor) params.cursor = cursor;
  if (filters.pageSize) params.page_size = filters.pageSize;

  const response = await apiClient.get<CursorPage<ItemSummary>>('/items', { params });
  return response.data;
}

export async function getItem(id: string): Promise<ItemDetail> {
  const response = await apiClient.get<ItemDetail>(`/items/${id}`);
  return response.data;
}

export async function getCategories(): Promise<TagTypeRecord[]> {
  const response = await apiClient.get<TagTypeRecord[]>('/taxonomy/tag-types');
  return response.data;
}

export async function getOccasions(): Promise<TagTypeRecord> {
  const response = await apiClient.get<TagTypeRecord>('/taxonomy/occasions');
  return response.data;
}

export async function getRelationships(): Promise<string[]> {
  const response = await apiClient.get<string[]>('/taxonomy/relationships');
  return response.data;
}
