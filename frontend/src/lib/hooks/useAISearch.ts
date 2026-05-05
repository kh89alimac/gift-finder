'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { aiSearch } from '../api/search';
import type { AISearchResponse, RecipientProfile } from '../types/api';

export function useAISearch() {
  const [lastResult, setLastResult] = useState<AISearchResponse | null>(null);

  const mutation = useMutation({
    mutationFn: ({
      query,
      profile,
    }: {
      query: string;
      profile?: Partial<RecipientProfile>;
    }) => aiSearch(query, profile),
    onSuccess: (data) => {
      setLastResult(data);
    },
  });

  return {
    search: mutation.mutate,
    searchAsync: mutation.mutateAsync,
    result: lastResult,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error,
    reset: () => {
      mutation.reset();
      setLastResult(null);
    },
  };
}
