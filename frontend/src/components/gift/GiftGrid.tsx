'use client';

import { useEffect, useRef } from 'react';
import { useDiscovery } from '../../lib/hooks/useDiscovery';
import GiftCard from './GiftCard';

interface GiftGridProps {
  wishlisted?: Set<string>;
  onWishlistToggle?: (itemId: string, wishlisted: boolean) => void;
}

export default function GiftGrid({ wishlisted = new Set(), onWishlistToggle }: GiftGridProps) {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError } =
    useDiscovery();

  const sentinelRef = useRef<HTMLDivElement>(null);

  // IntersectionObserver sentinel for infinite scroll
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { rootMargin: '200px' }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  if (isLoading) {
    return <GiftGridSkeleton />;
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-warm-600">
        <span className="text-5xl mb-4" aria-hidden="true">😕</span>
        <p className="text-lg font-medium">Something went wrong</p>
        <p className="text-sm mt-1">Please try refreshing the page.</p>
      </div>
    );
  }

  const allItems = data?.pages.flatMap((page) => page.items) ?? [];

  if (allItems.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-warm-600">
        <span className="text-5xl mb-4" aria-hidden="true">🎁</span>
        <p className="text-lg font-medium">No gifts found</p>
        <p className="text-sm mt-1">Try adjusting your filters.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
        role="list"
        aria-label="Gift results"
      >
        {allItems.map((item) => (
          <div key={item.id} role="listitem">
            <GiftCard
              item={item}
              isWishlisted={wishlisted.has(item.id)}
              onWishlistToggle={onWishlistToggle}
            />
          </div>
        ))}
      </div>

      {/* Infinite scroll sentinel */}
      <div ref={sentinelRef} className="flex justify-center py-4">
        {isFetchingNextPage && (
          <div className="flex items-center gap-2 text-warm-500">
            <div className="h-4 w-4 rounded-full border-2 border-gift-400 border-t-transparent animate-spin" />
            <span className="text-sm">Loading more gifts…</span>
          </div>
        )}
        {!hasNextPage && allItems.length > 0 && (
          <p className="text-sm text-warm-400">You&apos;ve seen all {allItems.length} gifts</p>
        )}
      </div>
    </div>
  );
}

function GiftGridSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {Array.from({ length: 12 }).map((_, i) => (
        <div
          key={i}
          className="rounded-2xl border border-warm-200 overflow-hidden bg-white"
          aria-hidden="true"
        >
          <div className="aspect-[4/3] skeleton" />
          <div className="p-4 flex flex-col gap-2">
            <div className="skeleton h-4 rounded w-full" />
            <div className="skeleton h-4 rounded w-3/4" />
            <div className="skeleton h-5 rounded w-1/3" />
            <div className="flex gap-1">
              <div className="skeleton h-5 rounded-full w-16" />
              <div className="skeleton h-5 rounded-full w-12" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
