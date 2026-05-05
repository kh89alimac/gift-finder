'use client';

import { create } from 'zustand';

interface WishlistStore {
  pendingAdd: Set<string>;
  pendingRemove: Set<string>;
  addOptimistic: (itemId: string) => void;
  removeOptimistic: (itemId: string) => void;
  confirmAdd: (itemId: string) => void;
  confirmRemove: (itemId: string) => void;
  rollback: (itemId: string) => void;
  isAdding: (itemId: string) => boolean;
  isRemoving: (itemId: string) => boolean;
}

const useWishlistStore = create<WishlistStore>((set, get) => ({
  pendingAdd: new Set<string>(),
  pendingRemove: new Set<string>(),

  addOptimistic: (itemId: string) => {
    set((state) => ({
      pendingAdd: new Set([...state.pendingAdd, itemId]),
      pendingRemove: new Set([...state.pendingRemove].filter((id) => id !== itemId)),
    }));
  },

  removeOptimistic: (itemId: string) => {
    set((state) => ({
      pendingRemove: new Set([...state.pendingRemove, itemId]),
      pendingAdd: new Set([...state.pendingAdd].filter((id) => id !== itemId)),
    }));
  },

  confirmAdd: (itemId: string) => {
    set((state) => ({
      pendingAdd: new Set([...state.pendingAdd].filter((id) => id !== itemId)),
    }));
  },

  confirmRemove: (itemId: string) => {
    set((state) => ({
      pendingRemove: new Set([...state.pendingRemove].filter((id) => id !== itemId)),
    }));
  },

  rollback: (itemId: string) => {
    set((state) => ({
      pendingAdd: new Set([...state.pendingAdd].filter((id) => id !== itemId)),
      pendingRemove: new Set([...state.pendingRemove].filter((id) => id !== itemId)),
    }));
  },

  isAdding: (itemId: string) => get().pendingAdd.has(itemId),
  isRemoving: (itemId: string) => get().pendingRemove.has(itemId),
}));

export default useWishlistStore;
