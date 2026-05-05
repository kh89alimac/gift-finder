'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  createTag,
  createTagType,
  deleteTag,
  deleteTagType,
  listTagTypes,
  listTags,
  mergeTags,
  updateTag,
  updateTagType,
} from '../../api/admin/taxonomy';

export function useTagTypes() {
  return useQuery({
    queryKey: ['admin', 'taxonomy', 'tag-types'],
    queryFn: listTagTypes,
    staleTime: 1000 * 60 * 5,
  });
}

export function useTags(tagTypeId?: string) {
  return useQuery({
    queryKey: ['admin', 'taxonomy', 'tags', tagTypeId],
    queryFn: () => listTags(tagTypeId),
    enabled: true,
    staleTime: 1000 * 60 * 5,
  });
}

export function useCreateTagType() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) => createTagType(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'taxonomy', 'tag-types'] });
      toast.success('Tag type created');
    },
    onError: () => toast.error('Failed to create tag type'),
  });
}

export function useUpdateTagType() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; description?: string } }) =>
      updateTagType(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'taxonomy', 'tag-types'] });
      toast.success('Tag type updated');
    },
    onError: () => toast.error('Failed to update tag type'),
  });
}

export function useDeleteTagType() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTagType(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'taxonomy', 'tag-types'] });
      toast.success('Tag type deleted');
    },
    onError: () => toast.error('Failed to delete tag type'),
  });
}

export function useCreateTag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; tagTypeId: string; description?: string }) => createTag(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'taxonomy', 'tags'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'taxonomy', 'tag-types'] });
      toast.success('Tag created');
    },
    onError: () => toast.error('Failed to create tag'),
  });
}

export function useUpdateTag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; description?: string } }) =>
      updateTag(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'taxonomy', 'tags'] });
      toast.success('Tag updated');
    },
    onError: () => toast.error('Failed to update tag'),
  });
}

export function useDeleteTag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTag(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'taxonomy', 'tags'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'taxonomy', 'tag-types'] });
      toast.success('Tag deleted');
    },
    onError: () => toast.error('Failed to delete tag'),
  });
}

export function useMergeTags() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sourceId, targetId }: { sourceId: string; targetId: string }) =>
      mergeTags(sourceId, targetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'taxonomy'] });
      toast.success('Tags merged successfully');
    },
    onError: () => toast.error('Failed to merge tags'),
  });
}
