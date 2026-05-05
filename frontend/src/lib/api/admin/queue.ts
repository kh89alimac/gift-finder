import apiClient from '../client';
import type { ApproveItemPatch, PaginatedResponse, ReviewQueueItem } from '../../types/api';

interface QueueFilters {
  status?: string;
  source?: string;
  page?: number;
  pageSize?: number;
}

export async function listQueue(filters: QueueFilters = {}): Promise<PaginatedResponse<ReviewQueueItem>> {
  const params: Record<string, unknown> = {};
  if (filters.status) params.status = filters.status;
  if (filters.source) params.source = filters.source;
  if (filters.page) params.page = filters.page;
  if (filters.pageSize) params.page_size = filters.pageSize;

  const response = await apiClient.get<PaginatedResponse<ReviewQueueItem>>('/admin/queue', { params });
  return response.data;
}

export async function approve(id: string, patch?: ApproveItemPatch): Promise<ReviewQueueItem> {
  const response = await apiClient.post<ReviewQueueItem>(`/admin/queue/${id}/approve`, patch ?? {});
  return response.data;
}

export async function reject(id: string, reason: string): Promise<ReviewQueueItem> {
  const response = await apiClient.post<ReviewQueueItem>(`/admin/queue/${id}/reject`, { reason });
  return response.data;
}

export async function bulkApprove(ids: string[]): Promise<{ approved: number }> {
  const response = await apiClient.post<{ approved: number }>('/admin/queue/bulk-approve', { ids });
  return response.data;
}

export async function bulkReject(ids: string[], reason: string): Promise<{ rejected: number }> {
  const response = await apiClient.post<{ rejected: number }>('/admin/queue/bulk-reject', { ids, reason });
  return response.data;
}
