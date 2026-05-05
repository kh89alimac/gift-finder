'use client';

import { useQuery } from '@tanstack/react-query';
import { getItem } from '../api/items';
import { getSimilarItems } from '../api/recommendations';

export function useItemDetail(id: string) {
  const itemQuery = useQuery({
    queryKey: ['item', id],
    queryFn: () => getItem(id),
    enabled: Boolean(id),
    staleTime: 1000 * 60 * 10,
  });

  const similarQuery = useQuery({
    queryKey: ['item', id, 'similar'],
    queryFn: () => getSimilarItems(id),
    enabled: Boolean(id) && itemQuery.isSuccess,
    staleTime: 1000 * 60 * 10,
  });

  return {
    item: itemQuery.data,
    similarItems: similarQuery.data ?? [],
    isLoading: itemQuery.isLoading,
    isSimilarLoading: similarQuery.isLoading,
    error: itemQuery.error,
  };
}
