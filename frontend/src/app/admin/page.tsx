'use client';

import { useQuery } from '@tanstack/react-query';
import apiClient from '../../lib/api/client';

interface AdminStats {
  pendingReviews: number;
  activeItems: number;
  scraperJobsToday: number;
  totalUsers: number;
}

function useAdminStats() {
  return useQuery<AdminStats>({
    queryKey: ['admin', 'stats'],
    queryFn: async () => {
      const response = await apiClient.get<AdminStats>('/admin/stats');
      return response.data;
    },
    // Fallback if endpoint doesn't exist yet
    retry: false,
  });
}

const statCards = [
  {
    key: 'pendingReviews' as keyof AdminStats,
    label: 'Pending Reviews',
    icon: '📋',
    href: '/admin/queue',
    color: 'bg-yellow-50 border-yellow-200',
    valueColor: 'text-yellow-700',
  },
  {
    key: 'activeItems' as keyof AdminStats,
    label: 'Active Items',
    icon: '📦',
    href: '/admin/items',
    color: 'bg-green-50 border-green-200',
    valueColor: 'text-green-700',
  },
  {
    key: 'scraperJobsToday' as keyof AdminStats,
    label: 'Scraper Jobs Today',
    icon: '🤖',
    href: '/admin/ingestion',
    color: 'bg-blue-50 border-blue-200',
    valueColor: 'text-blue-700',
  },
  {
    key: 'totalUsers' as keyof AdminStats,
    label: 'Total Users',
    icon: '👥',
    href: undefined,
    color: 'bg-purple-50 border-purple-200',
    valueColor: 'text-purple-700',
  },
];

export default function AdminDashboard() {
  const { data: stats, isLoading } = useAdminStats();

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-warm-950">Dashboard</h1>
        <p className="text-sm text-warm-500 mt-0.5">Overview of your Gift Finder platform</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {statCards.map((card) => (
          <div
            key={card.key}
            className={`rounded-2xl border ${card.color} p-5`}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-2xl" aria-hidden="true">{card.icon}</span>
              {card.href && (
                <a
                  href={card.href}
                  className="text-xs text-warm-400 hover:text-warm-600 transition-colors"
                >
                  View →
                </a>
              )}
            </div>
            {isLoading ? (
              <div className="skeleton h-8 w-16 rounded mb-1" />
            ) : (
              <p className={`text-3xl font-bold ${card.valueColor}`}>
                {stats?.[card.key] ?? '—'}
              </p>
            )}
            <p className="text-sm text-warm-600 mt-1">{card.label}</p>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div className="rounded-2xl border border-warm-200 bg-white p-6">
        <h2 className="text-base font-semibold text-warm-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {[
            { label: 'Review pending items', href: '/admin/queue', desc: 'Approve or reject scraped items' },
            { label: 'Manage taxonomy', href: '/admin/taxonomy', desc: 'Add/edit tags and categories' },
            { label: 'Trigger scraper', href: '/admin/ingestion', desc: 'Run a manual scrape job' },
            { label: 'Import CSV', href: '/admin/ingestion', desc: 'Bulk import items from CSV' },
            { label: 'View all items', href: '/admin/items', desc: 'Browse and manage the catalog' },
          ].map((action) => (
            <a
              key={action.href + action.label}
              href={action.href}
              className="flex flex-col gap-1 rounded-xl border border-warm-100 bg-warm-50 px-4 py-3 hover:bg-warm-100 hover:border-warm-200 transition-colors"
            >
              <span className="text-sm font-medium text-warm-900">{action.label}</span>
              <span className="text-xs text-warm-500">{action.desc}</span>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
