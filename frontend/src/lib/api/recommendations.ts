import apiClient from './client';
import type { ItemSummary, RecipientProfile } from '../types/api';

export async function getRecommendations(profile: Partial<RecipientProfile>): Promise<ItemSummary[]> {
  const response = await apiClient.post<ItemSummary[]>('/recommendations', profile);
  return response.data;
}

export async function getSimilarItems(itemId: string): Promise<ItemSummary[]> {
  const response = await apiClient.get<ItemSummary[]>(`/items/${itemId}/similar`);
  return response.data;
}
