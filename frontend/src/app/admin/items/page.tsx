'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { listAdminItems, updateItemStatus } from '../../../lib/api/admin/ingestion';
import { formatPrice, formatDate } from '../../../lib/utils/format';
import { cn } from '../../../lib/utils/cn';
import type { ItemStatus } from '../../../lib/types/api';

const STATUS_OPTIONS: { value: ItemStatus | ''; label: string }[] = [
  { value: '', label: 'All Status' },
  { value: 'approved', label: 'Approved' },
  { value: 'pending', label: 'Pending' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'archived', label: 'Archived' },
];

const STATUS_COLORS: Record<ItemStatus, string> = {
  approved: 'bg-green-100 text-green-700',
  pending: 'bg-yellow-100 text-yellow-700',
  rejected: 'bg-blush-100 text-blush-700',
  archived: 'bg-warm-100 text-warm-500',
};

export default function AdminItemsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<ItemStatus | ''>('');
  const [page, setPage] = useState(1);

  // Simple debounce without external library
  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    const timer = setTimeout(() => {
      setDebouncedSearch(value);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, []);

  const { data, isLoading } = useQuery({
    queryKey: ['admin', 'items', { q: debouncedSearch, status: statusFilter, page }],
    queryFn: () => listAdminItems({
      q: debouncedSearch || undefined,
      status: statusFilter || undefined,
      page,
      pageSize: 25,
    }),
  });

  const { mutate: changeStatus } = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateItemStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'items'] });
      toast.success('Status updated');
    },
    onError: () => toast.error('Failed to update status'),
  });

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-warm-950">Items</h1>
          <p className="text-sm text-warm-500 mt-0.5">{data?.total ?? 0} total items</p>
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          <input
            type="search"
            placeholder="Search items…"
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="rounded-lg border border-warm-200 px-4 py-2 text-sm focus:border-gift-400 focus:outline-none"
            aria-label="Search items"
          />
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value as ItemStatus | ''); setPage(1); }}
            className="rounded-lg border border-warm-200 bg-white px-3 py-2 text-sm focus:border-gift-400 focus:outline-none"
            aria-label="Filter by status"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="skeleton h-14 rounded-xl" aria-hidden="true" />
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-warm-200 overflow-hidden">
          {!data?.items.length ? (
            <div className="py-12 text-center text-warm-400">
              <span className="text-4xl block mb-3" aria-hidden="true">📭</span>
              <p className="text-sm">No items found</p>
            </div>
          ) : (
            <table className="w-full text-sm" aria-label="Items list">
              <thead className="bg-warm-50 border-b border-warm-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-warm-600 w-12 hidden sm:table-cell">
                    <span className="sr-only">Image</span>
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-warm-600">Item</th>
                  <th className="text-right px-4 py-3 font-medium text-warm-600">Price</th>
                  <th className="text-center px-4 py-3 font-medium text-warm-600">Status</th>
                  <th className="text-center px-4 py-3 font-medium text-warm-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-warm-100">
                {data.items.map((item) => {
                  const added = formatDate(item.createdAt);
                  return (
                    <tr key={item.id} className="hover:bg-warm-50 transition-colors">
                      {/* Thumbnail */}
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <div className="relative h-10 w-10 rounded-lg overflow-hidden bg-warm-100">
                          {item.imageUrl ? (
                            <Image
                              src={item.imageUrl}
                              alt=""
                              fill
                              className="object-cover"
                              sizes="40px"
                            />
                          ) : (
                            <span className="absolute inset-0 flex items-center justify-center text-lg" aria-hidden="true">🎁</span>
                          )}
                        </div>
                      </td>

                      {/* Title */}
                      <td className="px-4 py-3">
                        <p className="font-medium text-warm-900 line-clamp-1">{item.title}</p>
                        <p className="text-xs text-warm-400">{item.retailer} · <span title={added.absolute}>{added.relative}</span></p>
                      </td>

                      {/* Price */}
                      <td className="px-4 py-3 text-right font-semibold text-gift-600">
                        {formatPrice(item.price, item.currency)}
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3 text-center">
                        <select
                          value={item.status}
                          onChange={(e) => changeStatus({ id: item.id, status: e.target.value })}
                          className={cn(
                            'rounded-full border-0 px-2 py-0.5 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-gift-400',
                            STATUS_COLORS[item.status]
                          )}
                          aria-label={`Status for ${item.title}`}
                        >
                          <option value="approved">Approved</option>
                          <option value="pending">Pending</option>
                          <option value="rejected">Rejected</option>
                          <option value="archived">Archived</option>
                        </select>
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3 text-center">
                        <Link
                          href={`/item/${item.id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-warm-400 hover:text-gift-600 transition-colors"
                          aria-label={`View ${item.title}`}
                        >
                          <svg className="h-4 w-4 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Pagination */}
      {data && data.totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-warm-500">
            Page {data.page} of {data.totalPages} ({data.total} items)
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              disabled={page === 1}
              className="rounded-full border border-warm-200 px-4 py-2 text-sm font-medium text-warm-700 hover:bg-warm-50 disabled:opacity-50"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(p + 1, data.totalPages))}
              disabled={page === data.totalPages}
              className="rounded-full border border-warm-200 px-4 py-2 text-sm font-medium text-warm-700 hover:bg-warm-50 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
