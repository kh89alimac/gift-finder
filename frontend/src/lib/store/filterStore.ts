'use client';

import { create } from 'zustand';
import type { SortOption } from '../types/api';

interface FilterState {
  ageMin: number | null;
  ageMax: number | null;
  relationship: string | null;
  occasion: string[];
  interests: string[];
  budgetMin: number | null;
  budgetMax: number | null;
  sort: SortOption;
}

interface FilterStore extends FilterState {
  setFilter: <K extends keyof FilterState>(key: K, value: FilterState[K]) => void;
  resetFilters: () => void;
  hasActiveFilters: () => boolean;
}

const defaultFilters: FilterState = {
  ageMin: null,
  ageMax: null,
  relationship: null,
  occasion: [],
  interests: [],
  budgetMin: null,
  budgetMax: null,
  sort: 'relevance',
};

const useFilterStore = create<FilterStore>((set, get) => ({
  ...defaultFilters,

  setFilter: <K extends keyof FilterState>(key: K, value: FilterState[K]) => {
    set({ [key]: value } as Pick<FilterState, K>);
  },

  resetFilters: () => {
    set({ ...defaultFilters });
  },

  hasActiveFilters: () => {
    const state = get();
    return (
      state.ageMin !== null ||
      state.ageMax !== null ||
      state.relationship !== null ||
      state.occasion.length > 0 ||
      state.interests.length > 0 ||
      state.budgetMin !== null ||
      state.budgetMax !== null ||
      state.sort !== 'relevance'
    );
  },
}));

export default useFilterStore;
