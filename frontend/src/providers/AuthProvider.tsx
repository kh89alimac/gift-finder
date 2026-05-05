'use client';

import { useEffect } from 'react';
import useAuthStore from '../lib/store/authStore';
import { injectAuthStore } from '../lib/api/client';
import { getMe } from '../lib/api/auth';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { accessToken, updateToken, clearAuth, setAuth } = useAuthStore();

  // Inject auth store into the axios client once on mount
  useEffect(() => {
    injectAuthStore(
      () => useAuthStore.getState().accessToken,
      (token: string) => useAuthStore.getState().updateToken(token),
      () => useAuthStore.getState().clearAuth()
    );
  }, []);

  // If we have a persisted user but no in-memory access token, ask the API
  // to mint one using the httpOnly refresh cookie. The browser sends the
  // cookie automatically because of `withCredentials: true`.
  useEffect(() => {
    const { user } = useAuthStore.getState();

    if (user && !accessToken) {
      // Import lazily to avoid circular reference at module load
      import('../lib/api/auth').then(({ refreshToken: refreshFn }) => {
        refreshFn()
          .then((tokens) => {
            updateToken(tokens.accessToken);
            // Also refresh user data
            return getMe();
          })
          .then((freshUser) => {
            setAuth(freshUser, useAuthStore.getState().accessToken!);
          })
          .catch(() => {
            clearAuth();
          });
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <>{children}</>;
}
