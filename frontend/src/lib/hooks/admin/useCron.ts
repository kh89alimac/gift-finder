'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  createSchedule,
  deleteSchedule,
  disableSchedule,
  enableSchedule,
  listSchedules,
  triggerSchedule,
  updateSchedule,
} from '../../api/admin/cron';
import { getJob } from '../../api/admin/ingestion';
import type { CreateCronScheduleRequest, UpdateCronScheduleRequest } from '../../types/api';

const ACTIVE_STATUSES = new Set(['queued', 'running']);

export function useCronSchedules() {
  return useQuery({
    queryKey: ['admin', 'cron', 'schedules'],
    queryFn: listSchedules,
    staleTime: 30_000,
  });
}

export function useCreateCronSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateCronScheduleRequest) => createSchedule(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'cron', 'schedules'] });
      toast.success('Schedule created');
    },
    onError: () => toast.error('Failed to create schedule'),
  });
}

export function useUpdateCronSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateCronScheduleRequest }) =>
      updateSchedule(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'cron', 'schedules'] });
      toast.success('Schedule updated');
    },
    onError: () => toast.error('Failed to update schedule'),
  });
}

export function useDeleteCronSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteSchedule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'cron', 'schedules'] });
      toast.success('Schedule deleted');
    },
    onError: () => toast.error('Failed to delete schedule'),
  });
}

export function useTriggerCronSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => triggerSchedule(id),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'cron', 'schedules'] });
      toast.success(`Job started: ${job.id}`);
      // Start polling the triggered job
      queryClient.setQueryData(['admin', 'ingestion', 'job', job.id], job);
    },
    onError: () => toast.error('Failed to trigger schedule'),
  });
}

export function useEnableCronSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => enableSchedule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'cron', 'schedules'] });
      toast.success('Schedule enabled');
    },
    onError: () => toast.error('Failed to enable schedule'),
  });
}

export function useDisableCronSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => disableSchedule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'cron', 'schedules'] });
      toast.success('Schedule disabled');
    },
    onError: () => toast.error('Failed to disable schedule'),
  });
}

// Poll a specific job by ID - used to track job triggered from cron
export function useCronTriggeredJob(jobId: string | null) {
  return useQuery({
    queryKey: ['admin', 'ingestion', 'job', jobId],
    queryFn: () => getJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job) return false;
      return ACTIVE_STATUSES.has(job.status) ? 5000 : false;
    },
  });
}
