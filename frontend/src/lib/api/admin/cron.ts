import apiClient from '../client';
import type { CreateCronScheduleRequest, CronSchedule, ScraperJob, UpdateCronScheduleRequest } from '../../types/api';

export async function listSchedules(): Promise<CronSchedule[]> {
  const response = await apiClient.get<CronSchedule[]>('/admin/cron/schedules');
  return response.data;
}

export async function getSchedule(id: string): Promise<CronSchedule> {
  const response = await apiClient.get<CronSchedule>(`/admin/cron/schedules/${id}`);
  return response.data;
}

export async function createSchedule(data: CreateCronScheduleRequest): Promise<CronSchedule> {
  const response = await apiClient.post<CronSchedule>('/admin/cron/schedules', data);
  return response.data;
}

export async function updateSchedule(
  id: string,
  data: UpdateCronScheduleRequest
): Promise<CronSchedule> {
  const response = await apiClient.patch<CronSchedule>(`/admin/cron/schedules/${id}`, data);
  return response.data;
}

export async function deleteSchedule(id: string): Promise<void> {
  await apiClient.delete(`/admin/cron/schedules/${id}`);
}

export async function triggerSchedule(id: string): Promise<ScraperJob> {
  const response = await apiClient.post<ScraperJob>(`/admin/cron/schedules/${id}/trigger`);
  return response.data;
}

export async function enableSchedule(id: string): Promise<CronSchedule> {
  const response = await apiClient.post<CronSchedule>(`/admin/cron/schedules/${id}/enable`);
  return response.data;
}

export async function disableSchedule(id: string): Promise<CronSchedule> {
  const response = await apiClient.post<CronSchedule>(`/admin/cron/schedules/${id}/disable`);
  return response.data;
}
