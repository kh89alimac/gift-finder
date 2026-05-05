'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { User } from '../types/api';

interface AuthStore {
  user: User | null;
  accessToken: string | null;
  setAuth: (user: User, token: string) => void;
  updateToken: (token: string) => void;
  clearAuth: () => void;
  isAdmin: () => boolean;
  isAuthenticated: () => boolean;
}

// We persist only user (not the access token) to localStorage for security.
// The access token lives only in memory (Zustand state, not persisted).
const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,

      setAuth: (user: User, token: string) => {
        set({ user, accessToken: token });
      },

      updateToken: (token: string) => {
        set({ accessToken: token });
      },

      clearAuth: () => {
        set({ user: null, accessToken: null });
      },

      isAdmin: () => {
        const { user } = get();
        return user?.role === 'admin';
      },

      isAuthenticated: () => {
        const { user } = get();
        return user !== null;
      },
    }),
    {
      name: 'gift-finder-auth',
      storage: createJSONStorage(() =>
        typeof window !== 'undefined' ? localStorage : {
          getItem: () => null,
          setItem: () => undefined,
          removeItem: () => undefined,
        }
      ),
      // Only persist user, NOT accessToken
      partialize: (state) => ({ user: state.user }),
    }
  )
);

export default useAuthStore;
