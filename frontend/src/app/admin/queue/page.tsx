'use client';

import { useState } from 'react';
import ReviewQueueTable from '../../../components/admin/ReviewQueueTable';
import BulkActionBar from '../../../components/admin/BulkActionBar';
import {
  useReviewQueue,
  useApproveItem,
  useRejectItem,
  useBulkApprove,
  useBulkReject,
} from '../../../lib/hooks/admin/useReviewQueue';
import useAdminStore from '../../../lib/store/adminStore';

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
];

const SOURCE_OPTIONS = [
  { value: '', label: 'All Sources' },
  { value: 'scraper', label: 'Scraper' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'manual', label: 'Manual' },
  { value: 'csv', label: 'CSV' },
];

export default function ReviewQueuePage() {
  const [statusFilter, setStatusFilter] = useState('pending');
  const [sourceFilter, setSourceFilter] = useState('');
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useReviewQueue({
    status: statusFilter || undefined,
    source: sourceFilter || undefined,
    page,
    pageSize: 20,
  });

  const { mutate: approveItem, variables: approvingVars } = useApproveItem();
  const { mutate: rejectItem, variables: rejectingVars } = useRejectItem();
  const { mutate: bulkApprove, isPending: isBulkApproving } = useBulkApprove();
  const { mutate: bulkReject, isPending: isBulkRejecting } = useBulkReject();
  const { selectedIds } = useAdminStore();

  return (
    <div className="pb-24">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-warm-950">Review Queue</h1>
          <p className="text-sm text-warm-500 mt-0.5">
            {data?.total ?? 0} items to review
          </p>
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-warm-200 bg-white px-3 py-2 text-sm focus:border-gift-400 focus:outline-none"
            aria-label="Filter by status"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <select
            value={sourceFilter}
            onChange={(e) => { setSourceFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-warm-200 bg-white px-3 py-2 text-sm focus:border-gift-400 focus:outline-none"
            aria-label="Filter by source"
          >
            {SOURCE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="skeleton h-16 rounded-xl" aria-hidden="true" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-2xl border border-blush-200 bg-blush-50 p-6 text-center">
          <p className="text-blush-700">Failed to load review queue. Please refresh.</p>
        </div>
      ) : (
        <>
          <ReviewQueueTable
            items={data?.items ?? []}
            onApprove={(id) => approveItem({ id })}
            onReject={(id, reason) => rejectItem({ id, reason })}
            isApprovingId={approvingVars?.id ?? null}
            isRejectingId={rejectingVars?.id ?? null}
          />

          {/* Pagination */}
          {data && data.totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-warm-500">
                Page {data.page} of {data.totalPages}
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
        </>
      )}

      {/* Bulk action bar */}
      {selectedIds.size > 0 && (
        <BulkActionBar
          onApprove={(ids) => bulkApprove(ids)}
          onReject={(ids, reason) => bulkReject({ ids, reason })}
          isApproving={isBulkApproving}
          isRejecting={isBulkRejecting}
        />
      )}
    </div>
  );
}
