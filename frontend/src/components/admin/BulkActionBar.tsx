'use client';

import { useState } from 'react';
import useAdminStore from '../../lib/store/adminStore';

interface BulkActionBarProps {
  onApprove: (ids: string[]) => void;
  onReject: (ids: string[], reason: string) => void;
  isApproving?: boolean;
  isRejecting?: boolean;
}

export default function BulkActionBar({
  onApprove,
  onReject,
  isApproving = false,
  isRejecting = false,
}: BulkActionBarProps) {
  const { selectedIds, clearSelection, count } = useAdminStore();
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const selectedCount = count();

  if (selectedCount === 0) return null;

  function handleRejectSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!rejectReason.trim()) return;
    onReject([...selectedIds], rejectReason.trim());
    setRejectDialogOpen(false);
    setRejectReason('');
  }

  return (
    <>
      {/* Fixed bottom bar */}
      <div
        className="fixed bottom-0 left-0 right-0 z-30 bg-warm-950 text-white px-6 py-4 shadow-2xl"
        role="region"
        aria-label="Bulk actions"
        aria-live="polite"
      >
        <div className="mx-auto max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-3">
          <span className="text-sm font-medium">
            {selectedCount} {selectedCount === 1 ? 'item' : 'items'} selected
          </span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={clearSelection}
              className="rounded-full border border-white/20 px-4 py-2 text-sm font-medium text-white/80 hover:text-white hover:bg-white/10 transition-colors"
            >
              Clear selection
            </button>
            <button
              type="button"
              onClick={() => setRejectDialogOpen(true)}
              disabled={isRejecting}
              className="rounded-full border border-blush-400 bg-blush-500 px-5 py-2 text-sm font-semibold text-white hover:bg-blush-600 disabled:opacity-50 transition-colors"
            >
              {isRejecting ? 'Rejecting…' : `Reject ${selectedCount} items`}
            </button>
            <button
              type="button"
              onClick={() => onApprove([...selectedIds])}
              disabled={isApproving}
              className="rounded-full bg-green-500 px-5 py-2 text-sm font-semibold text-white hover:bg-green-600 disabled:opacity-50 transition-colors"
            >
              {isApproving ? 'Approving…' : `Approve ${selectedCount} items`}
            </button>
          </div>
        </div>
      </div>

      {/* Reject dialog */}
      {rejectDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4" role="dialog" aria-modal="true" aria-labelledby="reject-title">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setRejectDialogOpen(false)}
            aria-hidden="true"
          />
          <div className="relative z-10 w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h2 id="reject-title" className="text-lg font-semibold text-warm-950 mb-4">
              Reject {selectedCount} {selectedCount === 1 ? 'item' : 'items'}
            </h2>
            <form onSubmit={handleRejectSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="reject-reason" className="text-sm font-medium text-warm-700">
                  Rejection reason <span className="text-blush-500">*</span>
                </label>
                <textarea
                  id="reject-reason"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  required
                  rows={3}
                  placeholder="e.g. Low quality image, duplicate item, out of stock…"
                  className="rounded-lg border border-warm-200 px-4 py-2.5 text-sm resize-none focus:border-blush-400 focus:outline-none"
                />
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setRejectDialogOpen(false)}
                  className="rounded-full border border-warm-200 px-5 py-2 text-sm font-medium text-warm-700 hover:bg-warm-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!rejectReason.trim()}
                  className="rounded-full bg-blush-500 px-5 py-2 text-sm font-semibold text-white hover:bg-blush-600 disabled:opacity-50"
                >
                  Reject Items
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
