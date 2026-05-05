'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  getJob,
  importCSV,
  listInstagramQueue,
  listJobs,
  listSites,
  triggerInstagram,
  triggerScraper,
} from '../../api/admin/ingestion';
import type { InstagramTargetType } from '../../types/api';

const ACTIVE_JOB_STATUSES = new Set(['queued', 'running']);

export function useScraperSites() {
  return useQuery({
    queryKey: ['admin', 'ingestion', 'sites'],
    queryFn: listSites,
    staleTime: 1000 * 60 * 5,
  });
}

export function useScraperJobs(filters: { status?: string; siteId?: string; page?: number } = {}) {
  const data = useQuery({
    queryKey: ['admin', 'ingestion', 'jobs', filters],
    queryFn: () => listJobs(filters),
    // Poll every 5 seconds if the query key doesn't have a specific status filter
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const hasActiveJobs = items.some((job) => ACTIVE_JOB_STATUSES.has(job.status));
      return hasActiveJobs ? 5000 : false;
    },
  });

  return data;
}

export function useJob(id: string) {
  const data = useQuery({
    queryKey: ['admin', 'ingestion', 'job', id],
    queryFn: () => getJob(id),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job) return false;
      return ACTIVE_JOB_STATUSES.has(job.status) ? 5000 : false;
    },
  });

  return data;
}

export function useTriggerScraper() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (siteId: string) => triggerScraper(siteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'ingestion', 'jobs'] });
      toast.success('Scraper job started');
    },
    onError: () => {
      toast.error('Failed to trigger scraper');
    },
  });
}

export function useInstagramQueue() {
  return useQuery({
    queryKey: ['admin', 'ingestion', 'instagram'],
    queryFn: listInstagramQueue,
    refetchInterval: (query) => {
      const items = query.state.data ?? [];
      const hasActive = items.some((item) => ACTIVE_JOB_STATUSES.has(item.status));
      return hasActive ? 5000 : false;
    },
  });
}

export function useTriggerInstagram() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ target, type }: { target: string; type: InstagramTargetType }) =>
      triggerInstagram(target, type),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'ingestion', 'instagram'] });
      toast.success('Instagram job queued');
    },
    onError: () => {
      toast.error('Failed to queue Instagram job');
    },
  });
}

export function useImportCSV() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => importCSV(file),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'ingestion', 'jobs'] });
      toast.success(`CSV imported — ${data.itemsQueued} items queued`);
    },
    onError: () => {
      toast.error('CSV import failed');
    },
  });
}
