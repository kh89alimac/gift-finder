'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  approve,
  bulkApprove,
  bulkReject,
  listQueue,
  reject,
} from '../../api/admin/queue';
import useAdminStore from '../../store/adminStore';
import type { ApproveItemPatch } from '../../types/api';

interface QueueFilters {
  status?: string;
  source?: string;
  page?: number;
  pageSize?: number;
}

export function useReviewQueue(filters: QueueFilters = {}) {
  return useQuery({
    queryKey: ['admin', 'queue', filters],
    queryFn: () => listQueue(filters),
    staleTime: 30_000,
  });
}

export function useApproveItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch?: ApproveItemPatch }) =>
      approve(id, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'queue'] });
      toast.success('Item approved');
    },
    onError: () => {
      toast.error('Failed to approve item');
    },
  });
}

export function useRejectItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      reject(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'queue'] });
      toast.success('Item rejected');
    },
    onError: () => {
      toast.error('Failed to reject item');
    },
  });
}

export function useBulkApprove() {
  const queryClient = useQueryClient();
  const { clearSelection } = useAdminStore();

  return useMutation({
    mutationFn: (ids: string[]) => bulkApprove(ids),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'queue'] });
      clearSelection();
      toast.success(`Approved ${data.approved} items`);
    },
    onError: () => {
      toast.error('Bulk approve failed');
    },
  });
}

export function useBulkReject() {
  const queryClient = useQueryClient();
  const { clearSelection } = useAdminStore();

  return useMutation({
    mutationFn: ({ ids, reason }: { ids: string[]; reason: string }) =>
      bulkReject(ids, reason),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'queue'] });
      clearSelection();
      toast.success(`Rejected ${data.rejected} items`);
    },
    onError: () => {
      toast.error('Bulk reject failed');
    },
  });
}
