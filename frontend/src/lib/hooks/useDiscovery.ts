'use client';

import { useInfiniteQuery } from '@tanstack/react-query';
import { listItems } from '../api/items';
import useFilterStore from '../store/filterStore';
import type { CursorPage, ItemSummary } from '../types/api';

export function useDiscovery() {
  const filters = useFilterStore((state) => ({
    ageMin: state.ageMin,
    ageMax: state.ageMax,
    relationship: state.relationship,
    occasions: state.occasion,
    interests: state.interests,
    budgetMin: state.budgetMin,
    budgetMax: state.budgetMax,
    sort: state.sort,
  }));

  return useInfiniteQuery<CursorPage<ItemSummary>, Error>({
    queryKey: ['items', 'discovery', filters],
    queryFn: ({ pageParam }) => listItems(filters, pageParam as string | null | undefined),
    initialPageParam: null,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}
