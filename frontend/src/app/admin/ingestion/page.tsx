'use client';

import { useCallback, useState } from 'react';
import CronScheduleTable from '../../../components/admin/CronScheduleTable';
import {
  useScraperJobs,
  useScraperSites,
  useTriggerScraper,
  useImportCSV,
} from '../../../lib/hooks/admin/useIngestion';
import {
  useCronSchedules,
  useCreateCronSchedule,
  useDeleteCronSchedule,
  useDisableCronSchedule,
  useEnableCronSchedule,
  useTriggerCronSchedule,
} from '../../../lib/hooks/admin/useCron';
import { formatDate } from '../../../lib/utils/format';
import { cn } from '../../../lib/utils/cn';
import type { JobStatus } from '../../../lib/types/api';

const STATUS_COLORS: Record<JobStatus, string> = {
  queued: 'bg-blue-100 text-blue-700',
  running: 'bg-yellow-100 text-yellow-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-blush-100 text-blush-700',
  cancelled: 'bg-warm-100 text-warm-600',
};

export default function IngestionPage() {
  const { data: sites } = useScraperSites();
  const { data: jobs, isLoading: jobsLoading } = useScraperJobs();
  const { mutate: triggerScraper, variables: triggerVars, isPending: isTriggering } = useTriggerScraper();
  const { mutate: importCSV, isPending: isImporting } = useImportCSV();

  const { data: schedules, isLoading: schedulesLoading } = useCronSchedules();
  const { mutate: createSchedule } = useCreateCronSchedule();
  const { mutate: deleteSchedule } = useDeleteCronSchedule();
  const { mutate: triggerSchedule, variables: triggerScheduleVars, isPending: isTriggeringSchedule } = useTriggerCronSchedule();
  const { mutate: enableSchedule } = useEnableCronSchedule();
  const { mutate: disableSchedule } = useDisableCronSchedule();

  const [isDragOver, setIsDragOver] = useState(false);
  const [showCreateSchedule, setShowCreateSchedule] = useState(false);
  const [newSchedule, setNewSchedule] = useState({ name: '', expression: '0 2 * * *', taskType: 'scrape_all' });

  // CSV drop
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file && (file.name.endsWith('.csv') || file.type === 'text/csv')) {
        importCSV(file);
      }
    },
    [importCSV]
  );

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) importCSV(file);
  }

  function handleCreateSchedule(e: React.FormEvent) {
    e.preventDefault();
    if (!newSchedule.name.trim() || !newSchedule.expression.trim()) return;
    createSchedule(
      { name: newSchedule.name, expression: newSchedule.expression, taskType: newSchedule.taskType },
      { onSuccess: () => { setShowCreateSchedule(false); setNewSchedule({ name: '', expression: '0 2 * * *', taskType: 'scrape_all' }); } }
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-bold text-warm-950">Ingestion</h1>
        <p className="text-sm text-warm-500 mt-0.5">
          Manage scraper jobs, cron schedules, and CSV imports
        </p>
      </div>

      {/* Cron Schedules */}
      <section aria-labelledby="cron-heading">
        <div className="flex items-center justify-between mb-4">
          <h2 id="cron-heading" className="text-lg font-semibold text-warm-900">
            Cron Schedules
          </h2>
          <button
            type="button"
            onClick={() => setShowCreateSchedule(true)}
            className="inline-flex items-center gap-2 rounded-full bg-gift-500 px-4 py-2 text-sm font-semibold text-white hover:bg-gift-600 transition-colors"
          >
            + Add Schedule
          </button>
        </div>

        {showCreateSchedule && (
          <form
            onSubmit={handleCreateSchedule}
            className="rounded-2xl border border-warm-200 bg-white p-5 mb-4 flex flex-col gap-4 animate-slide-up"
          >
            <h3 className="text-sm font-semibold text-warm-900">New Cron Schedule</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-warm-600">Name</label>
                <input
                  type="text"
                  placeholder="Daily Scrape"
                  value={newSchedule.name}
                  onChange={(e) => setNewSchedule((p) => ({ ...p, name: e.target.value }))}
                  required
                  className="rounded-lg border border-warm-200 px-3 py-2 text-sm focus:border-gift-400 focus:outline-none"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-warm-600">Cron Expression</label>
                <input
                  type="text"
                  placeholder="0 2 * * *"
                  value={newSchedule.expression}
                  onChange={(e) => setNewSchedule((p) => ({ ...p, expression: e.target.value }))}
                  required
                  className="rounded-lg border border-warm-200 px-3 py-2 text-sm font-mono focus:border-gift-400 focus:outline-none"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-warm-600">Task Type</label>
                <input
                  type="text"
                  placeholder="scrape_all"
                  value={newSchedule.taskType}
                  onChange={(e) => setNewSchedule((p) => ({ ...p, taskType: e.target.value }))}
                  className="rounded-lg border border-warm-200 px-3 py-2 text-sm focus:border-gift-400 focus:outline-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowCreateSchedule(false)}
                className="rounded-full border border-warm-200 px-5 py-2 text-sm font-medium text-warm-700 hover:bg-warm-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-full bg-gift-500 px-5 py-2 text-sm font-semibold text-white hover:bg-gift-600"
              >
                Create
              </button>
            </div>
          </form>
        )}

        {schedulesLoading ? (
          <div className="skeleton h-40 rounded-2xl" aria-hidden="true" />
        ) : (
          <CronScheduleTable
            schedules={schedules ?? []}
            onTrigger={(id) => triggerSchedule(id)}
            onEnable={(id) => enableSchedule(id)}
            onDisable={(id) => disableSchedule(id)}
            onDelete={(id) => deleteSchedule(id)}
            isTriggeringId={isTriggeringSchedule ? triggerScheduleVars : null}
          />
        )}
      </section>

      {/* Manual Scraper Trigger */}
      <section aria-labelledby="scraper-heading">
        <h2 id="scraper-heading" className="text-lg font-semibold text-warm-900 mb-4">
          Manual Scraper
        </h2>
        <div className="flex flex-wrap gap-2 mb-6">
          {sites?.map((site) => (
            <button
              key={site.id}
              type="button"
              onClick={() => triggerScraper(site.id)}
              disabled={isTriggering && triggerVars === site.id}
              className="inline-flex items-center gap-2 rounded-full border border-warm-200 bg-white px-4 py-2 text-sm font-medium text-warm-700 hover:bg-warm-50 disabled:opacity-50 transition-colors"
            >
              {isTriggering && triggerVars === site.id ? (
                <div className="h-3 w-3 rounded-full border-2 border-gift-400 border-t-transparent animate-spin" />
              ) : (
                <span aria-hidden="true">🤖</span>
              )}
              Scrape {site.name}
            </button>
          ))}
          {!sites?.length && (
            <p className="text-sm text-warm-400">No scraper sites configured.</p>
          )}
        </div>

        {/* Jobs table */}
        {jobsLoading ? (
          <div className="skeleton h-40 rounded-2xl" aria-hidden="true" />
        ) : (
          <div className="rounded-2xl border border-warm-200 overflow-hidden">
            <div className="px-4 py-3 bg-warm-50 border-b border-warm-200">
              <h3 className="text-sm font-semibold text-warm-700">Recent Jobs</h3>
            </div>
            {!jobs?.items.length ? (
              <div className="py-8 text-center text-warm-400 text-sm">No jobs yet</div>
            ) : (
              <table className="w-full text-sm" aria-label="Scraper jobs">
                <thead className="border-b border-warm-100">
                  <tr>
                    <th className="text-left px-4 py-2.5 font-medium text-warm-500 text-xs">Site</th>
                    <th className="text-left px-4 py-2.5 font-medium text-warm-500 text-xs">Status</th>
                    <th className="text-right px-4 py-2.5 font-medium text-warm-500 text-xs hidden sm:table-cell">Items Found</th>
                    <th className="text-right px-4 py-2.5 font-medium text-warm-500 text-xs hidden sm:table-cell">Added</th>
                    <th className="text-right px-4 py-2.5 font-medium text-warm-500 text-xs">Started</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-warm-100">
                  {jobs.items.map((job) => {
                    const started = job.startedAt ? formatDate(job.startedAt) : null;
                    return (
                      <tr key={job.id} className="hover:bg-warm-50 transition-colors">
                        <td className="px-4 py-3 font-medium text-warm-800">{job.siteName}</td>
                        <td className="px-4 py-3">
                          <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium', STATUS_COLORS[job.status])}>
                            {job.status === 'running' && (
                              <span className="mr-1 inline-block h-2 w-2 rounded-full bg-yellow-500 animate-pulse" aria-hidden="true" />
                            )}
                            {job.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right text-warm-600 hidden sm:table-cell">{job.itemsFound}</td>
                        <td className="px-4 py-3 text-right text-warm-600 hidden sm:table-cell">{job.itemsAdded}</td>
                        <td className="px-4 py-3 text-right text-warm-400 text-xs">
                          {started ? <span title={started.absolute}>{started.relative}</span> : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}
      </section>

      {/* CSV Import */}
      <section aria-labelledby="csv-heading">
        <h2 id="csv-heading" className="text-lg font-semibold text-warm-900 mb-4">
          CSV Import
        </h2>
        <div
          className={cn(
            'rounded-2xl border-2 border-dashed transition-colors flex flex-col items-center justify-center py-12 gap-3',
            isDragOver ? 'border-gift-400 bg-gift-50' : 'border-warm-300 bg-warm-50',
            isImporting && 'opacity-60 pointer-events-none'
          )}
          onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          role="region"
          aria-label="CSV import drop zone"
        >
          {isImporting ? (
            <>
              <div className="h-8 w-8 rounded-full border-4 border-gift-300 border-t-gift-600 animate-spin" />
              <p className="text-sm text-warm-600 font-medium">Importing…</p>
            </>
          ) : (
            <>
              <span className="text-4xl" aria-hidden="true">📄</span>
              <div className="text-center">
                <p className="text-sm font-medium text-warm-700">
                  Drop a CSV file here or{' '}
                  <label className="text-gift-600 hover:text-gift-700 cursor-pointer underline">
                    browse
                    <input
                      type="file"
                      accept=".csv,text/csv"
                      className="sr-only"
                      onChange={handleFileInput}
                      aria-label="Select CSV file"
                    />
                  </label>
                </p>
                <p className="text-xs text-warm-400 mt-1">Accepts .csv files</p>
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
