'use client';

import { create } from 'zustand';

interface AdminStore {
  selectedIds: Set<string>;
  toggleSelect: (id: string) => void;
  selectAll: (ids: string[]) => void;
  clearSelection: () => void;
  isSelected: (id: string) => boolean;
  count: () => number;
}

const useAdminStore = create<AdminStore>((set, get) => ({
  selectedIds: new Set<string>(),

  toggleSelect: (id: string) => {
    set((state) => {
      const next = new Set(state.selectedIds);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return { selectedIds: next };
    });
  },

  selectAll: (ids: string[]) => {
    set({ selectedIds: new Set(ids) });
  },

  clearSelection: () => {
    set({ selectedIds: new Set<string>() });
  },

  isSelected: (id: string) => get().selectedIds.has(id),

  count: () => get().selectedIds.size,
}));

export default useAdminStore;
