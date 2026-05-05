'use client';

import Image from 'next/image';
import { useEffect, useRef, useState } from 'react';
import { cn } from '../../lib/utils/cn';
import useAdminStore from '../../lib/store/adminStore';
import { formatPrice } from '../../lib/utils/format';
import type { ReviewQueueItem } from '../../lib/types/api';

const SOURCE_ICONS: Record<string, string> = {
  scraper: '🤖',
  instagram: '📸',
  manual: '✏️',
  csv: '📄',
};

interface ReviewQueueTableProps {
  items: ReviewQueueItem[];
  onApprove: (id: string) => void;
  onReject: (id: string, reason: string) => void;
  isApprovingId?: string | null;
  isRejectingId?: string | null;
}

export default function ReviewQueueTable({
  items,
  onApprove,
  onReject,
  isApprovingId,
  isRejectingId,
}: ReviewQueueTableProps) {
  const { selectedIds, toggleSelect, selectAll, clearSelection, isSelected } = useAdminStore();
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);
  const [rejectDialogId, setRejectDialogId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const tableRef = useRef<HTMLDivElement>(null);

  // Keyboard navigation
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Ignore if focus is in an input/textarea
      const target = e.target as HTMLElement;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;

      if (focusedIndex < 0 || items.length === 0) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setFocusedIndex((i) => Math.min(i + 1, items.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setFocusedIndex((i) => Math.max(i - 1, 0));
          break;
        case 'a':
        case 'A': {
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            selectAll(items.map((item) => item.id));
          } else if (focusedIndex >= 0) {
            const item = items[focusedIndex];
            if (item) onApprove(item.id);
          }
          break;
        }
        case 'r':
        case 'R': {
          const item = items[focusedIndex];
          if (item) setRejectDialogId(item.id);
          break;
        }
        case ' ': {
          e.preventDefault();
          const item = items[focusedIndex];
          if (item) toggleSelect(item.id);
          break;
        }
        default:
          break;
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [focusedIndex, items, onApprove, selectAll, toggleSelect]);

  // Scroll focused row into view
  useEffect(() => {
    if (focusedIndex >= 0 && tableRef.current) {
      const row = tableRef.current.querySelector<HTMLElement>(
        `[data-row-index="${focusedIndex}"]`
      );
      row?.scrollIntoView({ block: 'nearest' });
    }
  }, [focusedIndex]);

  function handleRejectSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (rejectDialogId && rejectReason.trim()) {
      onReject(rejectDialogId, rejectReason.trim());
      setRejectDialogId(null);
      setRejectReason('');
    }
  }

  const allSelected = items.length > 0 && items.every((item) => selectedIds.has(item.id));

  return (
    <>
      <div
        ref={tableRef}
        className="rounded-2xl border border-warm-200 overflow-hidden"
        role="grid"
        aria-label="Review queue"
        tabIndex={0}
        onFocus={() => { if (focusedIndex < 0 && items.length > 0) setFocusedIndex(0); }}
      >
        {/* Header */}
        <div className="flex items-center gap-3 bg-warm-50 border-b border-warm-200 px-4 py-3">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={() => allSelected ? clearSelection() : selectAll(items.map((i) => i.id))}
            className="h-4 w-4 rounded border-warm-300 accent-gift-500"
            aria-label="Select all"
          />
          <div className="flex-1 grid grid-cols-[2fr_1fr_1fr_80px_130px] gap-4 text-xs font-semibold text-warm-500 uppercase tracking-wider">
            <span>Item</span>
            <span>Source</span>
            <span>Price</span>
            <span>Confidence</span>
            <span>Actions</span>
          </div>
        </div>

        {items.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <span className="text-4xl mb-3" aria-hidden="true">✅</span>
            <p className="text-warm-600 font-medium">Queue is empty</p>
            <p className="text-warm-400 text-sm mt-1">All items have been reviewed</p>
          </div>
        )}

        {items.map((item, index) => {
          const isFocused = index === focusedIndex;
          const selected = isSelected(item.id);

          return (
            <div
              key={item.id}
              data-row-id={item.id}
              data-row-index={index}
              className={cn(
                'flex items-center gap-3 border-b border-warm-100 last:border-b-0 px-4 py-3 cursor-pointer transition-colors',
                isFocused && 'ring-2 ring-inset ring-gift-400 bg-gift-50',
                selected && 'bg-gift-50',
                !isFocused && !selected && 'hover:bg-warm-50'
              )}
              onClick={() => setFocusedIndex(index)}
              role="row"
              aria-selected={selected}
              tabIndex={isFocused ? 0 : -1}
            >
              {/* Checkbox */}
              <input
                type="checkbox"
                checked={selected}
                onChange={(e) => { e.stopPropagation(); toggleSelect(item.id); }}
                className="h-4 w-4 rounded border-warm-300 accent-gift-500 flex-shrink-0"
                aria-label={`Select ${item.item.title}`}
              />

              <div className="flex-1 grid grid-cols-[2fr_1fr_1fr_80px_130px] gap-4 items-center min-w-0">
                {/* Item info */}
                <div className="flex items-center gap-3 min-w-0">
                  <div className="relative h-12 w-12 rounded-lg overflow-hidden bg-warm-100 flex-shrink-0">
                    {item.item.imageUrl ? (
                      <Image
                        src={item.item.imageUrl}
                        alt=""
                        fill
                        className="object-cover"
                        sizes="48px"
                      />
                    ) : (
                      <span className="absolute inset-0 flex items-center justify-center text-xl" aria-hidden="true">🎁</span>
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-warm-900 truncate" title={item.item.title}>
                      {item.item.title}
                    </p>
                    <p className="text-xs text-warm-400 truncate">{item.item.retailer}</p>
                  </div>
                </div>

                {/* Source */}
                <div className="flex items-center gap-1.5">
                  <span aria-hidden="true">{SOURCE_ICONS[item.source] ?? '📦'}</span>
                  <span className="text-xs text-warm-600 capitalize">{item.source}</span>
                </div>

                {/* Price */}
                <span className="text-sm font-semibold text-gift-600">
                  {formatPrice(item.item.price, item.item.currency)}
                </span>

                {/* Confidence */}
                <div>
                  {item.confidence !== null ? (
                    <div className="flex items-center gap-1.5">
                      <div className="flex-1 h-1.5 rounded-full bg-warm-200 overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full',
                            item.confidence >= 0.8 ? 'bg-green-500' :
                            item.confidence >= 0.5 ? 'bg-yellow-500' : 'bg-blush-500'
                          )}
                          style={{ width: `${(item.confidence * 100).toFixed(0)}%` }}
                        />
                      </div>
                      <span className="text-xs text-warm-500">
                        {(item.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ) : (
                    <span className="text-xs text-warm-300">—</span>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); onApprove(item.id); }}
                    disabled={isApprovingId === item.id}
                    className="rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700 hover:bg-green-200 disabled:opacity-50 transition-colors"
                    aria-label={`Approve ${item.item.title}`}
                  >
                    {isApprovingId === item.id ? '…' : 'Approve'}
                  </button>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); setRejectDialogId(item.id); }}
                    disabled={isRejectingId === item.id}
                    className="rounded-full bg-blush-100 px-3 py-1 text-xs font-semibold text-blush-700 hover:bg-blush-200 disabled:opacity-50 transition-colors"
                    aria-label={`Reject ${item.item.title}`}
                  >
                    Reject
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Keyboard hints */}
      <p className="mt-2 text-xs text-warm-400">
        Keyboard: ↑↓ navigate · A approve · R reject · Space select · Ctrl+A select all
      </p>

      {/* Reject dialog */}
      {rejectDialogId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center px-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reject-single-title"
        >
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setRejectDialogId(null)}
            aria-hidden="true"
          />
          <div className="relative z-10 w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h2 id="reject-single-title" className="text-lg font-semibold text-warm-950 mb-4">
              Reject Item
            </h2>
            <form onSubmit={handleRejectSubmit} className="flex flex-col gap-4">
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                required
                rows={3}
                placeholder="Reason for rejection…"
                autoFocus
                className="rounded-lg border border-warm-200 px-4 py-2.5 text-sm resize-none focus:border-blush-400 focus:outline-none"
                aria-label="Rejection reason"
              />
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setRejectDialogId(null)}
                  className="rounded-full border border-warm-200 px-5 py-2 text-sm font-medium text-warm-700 hover:bg-warm-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!rejectReason.trim()}
                  className="rounded-full bg-blush-500 px-5 py-2 text-sm font-semibold text-white hover:bg-blush-600 disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
