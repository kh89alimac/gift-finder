import apiClient from '../client';
import type { Tag, TagSlim, TagTypeRecord } from '../../types/api';

// ── Tag Types ──────────────────────────────────────────────────────────────
export async function listTagTypes(): Promise<TagTypeRecord[]> {
  const response = await apiClient.get<TagTypeRecord[]>('/admin/taxonomy/tag-types');
  return response.data;
}

export async function createTagType(data: { name: string; description?: string }): Promise<TagTypeRecord> {
  const response = await apiClient.post<TagTypeRecord>('/admin/taxonomy/tag-types', data);
  return response.data;
}

export async function updateTagType(
  id: string,
  data: { name?: string; description?: string }
): Promise<TagTypeRecord> {
  const response = await apiClient.patch<TagTypeRecord>(`/admin/taxonomy/tag-types/${id}`, data);
  return response.data;
}

export async function deleteTagType(id: string): Promise<void> {
  await apiClient.delete(`/admin/taxonomy/tag-types/${id}`);
}

// ── Tags ───────────────────────────────────────────────────────────────────
export async function listTags(tagTypeId?: string): Promise<Tag[]> {
  const params: Record<string, unknown> = {};
  if (tagTypeId) params.tag_type_id = tagTypeId;
  const response = await apiClient.get<Tag[]>('/admin/taxonomy/tags', { params });
  return response.data;
}

export async function createTag(data: {
  name: string;
  tagTypeId: string;
  description?: string;
}): Promise<Tag> {
  const response = await apiClient.post<Tag>('/admin/taxonomy/tags', data);
  return response.data;
}

export async function updateTag(
  id: string,
  data: { name?: string; description?: string }
): Promise<Tag> {
  const response = await apiClient.patch<Tag>(`/admin/taxonomy/tags/${id}`, data);
  return response.data;
}

export async function deleteTag(id: string): Promise<void> {
  await apiClient.delete(`/admin/taxonomy/tags/${id}`);
}

export async function mergeTags(sourceId: string, targetId: string): Promise<TagSlim> {
  const response = await apiClient.post<TagSlim>('/admin/taxonomy/tags/merge', { sourceId, targetId });
  return response.data;
}
