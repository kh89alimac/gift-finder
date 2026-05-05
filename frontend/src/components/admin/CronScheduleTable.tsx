'use client';

import { cn } from '../../lib/utils/cn';
import { parseCronToHuman, formatDate } from '../../lib/utils/format';
import type { CronSchedule } from '../../lib/types/api';

interface CronScheduleTableProps {
  schedules: CronSchedule[];
  onTrigger: (id: string) => void;
  onEnable: (id: string) => void;
  onDisable: (id: string) => void;
  onDelete: (id: string) => void;
  isTriggeringId?: string | null;
}

export default function CronScheduleTable({
  schedules,
  onTrigger,
  onEnable,
  onDisable,
  onDelete,
  isTriggeringId,
}: CronScheduleTableProps) {
  if (schedules.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center rounded-2xl border border-dashed border-warm-300">
        <span className="text-4xl mb-3" aria-hidden="true">⏰</span>
        <p className="text-warm-600 font-medium">No schedules yet</p>
        <p className="text-warm-400 text-sm mt-1">Create a cron schedule to automate scraping</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-warm-200 overflow-hidden">
      <table className="w-full text-sm" aria-label="Cron schedules">
        <thead className="bg-warm-50 border-b border-warm-200">
          <tr>
            <th className="text-left px-4 py-3 font-medium text-warm-600">Name</th>
            <th className="text-left px-4 py-3 font-medium text-warm-600">Schedule</th>
            <th className="text-left px-4 py-3 font-medium text-warm-600 hidden md:table-cell">Last Run</th>
            <th className="text-left px-4 py-3 font-medium text-warm-600 hidden md:table-cell">Next Run</th>
            <th className="text-center px-4 py-3 font-medium text-warm-600">Status</th>
            <th className="text-center px-4 py-3 font-medium text-warm-600">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-warm-100">
          {schedules.map((schedule) => {
            const humanSchedule = parseCronToHuman(schedule.expression);
            const lastRun = schedule.lastRunAt ? formatDate(schedule.lastRunAt) : null;
            const nextRun = schedule.nextRunAt ? formatDate(schedule.nextRunAt) : null;
            const isTriggering = isTriggeringId === schedule.id;

            return (
              <tr key={schedule.id} className="hover:bg-warm-50 transition-colors">
                <td className="px-4 py-3">
                  <div>
                    <p className="font-medium text-warm-900">{schedule.name}</p>
                    <p className="text-xs text-warm-400 font-mono">{schedule.expression}</p>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="text-warm-700">{humanSchedule}</span>
                </td>
                <td className="px-4 py-3 hidden md:table-cell">
                  {lastRun ? (
                    <span className="text-warm-500" title={lastRun.absolute}>
                      {lastRun.relative}
                    </span>
                  ) : (
                    <span className="text-warm-300">Never</span>
                  )}
                </td>
                <td className="px-4 py-3 hidden md:table-cell">
                  {nextRun ? (
                    <span className="text-warm-500" title={nextRun.absolute}>
                      {nextRun.absolute}
                    </span>
                  ) : (
                    <span className="text-warm-300">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-center">
                  <span
                    className={cn(
                      'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                      schedule.isActive
                        ? 'bg-green-100 text-green-700'
                        : 'bg-warm-100 text-warm-500'
                    )}
                  >
                    {schedule.isActive ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-center gap-2">
                    <button
                      type="button"
                      onClick={() => onTrigger(schedule.id)}
                      disabled={isTriggering}
                      className="rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-200 disabled:opacity-50 transition-colors"
                      aria-label={`Trigger ${schedule.name}`}
                    >
                      {isTriggering ? '…' : 'Run'}
                    </button>
                    {schedule.isActive ? (
                      <button
                        type="button"
                        onClick={() => onDisable(schedule.id)}
                        className="rounded-full bg-warm-100 px-3 py-1 text-xs font-medium text-warm-600 hover:bg-warm-200 transition-colors"
                        aria-label={`Disable ${schedule.name}`}
                      >
                        Pause
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => onEnable(schedule.id)}
                        className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700 hover:bg-green-200 transition-colors"
                        aria-label={`Enable ${schedule.name}`}
                      >
                        Enable
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        if (confirm(`Delete schedule "${schedule.name}"?`)) onDelete(schedule.id);
                      }}
                      className="text-warm-300 hover:text-blush-500 transition-colors"
                      aria-label={`Delete ${schedule.name}`}
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
