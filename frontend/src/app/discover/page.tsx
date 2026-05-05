'use client';

import { useState } from 'react';
import type { Metadata } from 'next';
import FilterPanel from '../../components/discovery/FilterPanel';
import ActiveFilters from '../../components/discovery/ActiveFilters';
import GiftGrid from '../../components/gift/GiftGrid';

// Note: metadata exported from client components is not supported in Next.js App Router.
// Use generateMetadata in a server wrapper if needed.

export default function DiscoverPage() {
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-warm-900">Discover Gifts</h1>
          <p className="text-sm text-warm-500 mt-0.5">
            Browse curated gifts matched to any profile
          </p>
        </div>

        {/* Mobile filter toggle */}
        <button
          type="button"
          onClick={() => setMobilePanelOpen(true)}
          className="md:hidden inline-flex items-center gap-2 rounded-full border border-warm-200 bg-white px-4 py-2 text-sm font-medium text-warm-700 shadow-sm hover:bg-warm-50 transition-colors"
          aria-label="Open filters"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
            />
          </svg>
          Filters
        </button>
      </div>

      {/* Active filter chips */}
      <ActiveFilters className="mb-4" />

      {/* Mobile drawer */}
      {mobilePanelOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setMobilePanelOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute bottom-0 left-0 right-0 max-h-[85vh] overflow-y-auto rounded-t-2xl bg-white shadow-xl">
            <FilterPanel
              isMobile
              onClose={() => setMobilePanelOpen(false)}
            />
          </div>
        </div>
      )}

      {/* Two-column layout */}
      <div className="flex gap-6">
        {/* Filter sidebar (desktop) */}
        <aside className="hidden md:block w-64 flex-shrink-0">
          <div className="sticky top-24">
            <FilterPanel />
          </div>
        </aside>

        {/* Gift grid */}
        <div className="flex-1 min-w-0">
          <GiftGrid />
        </div>
      </div>
    </div>
  );
}
