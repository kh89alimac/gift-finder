'use client';

import { useMutation } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { login, logout, register } from '../api/auth';
import useAuthStore from '../store/authStore';
import type { RegisterRequest } from '../types/api';

export function useLogin() {
  const { setAuth } = useAuthStore();
  const router = useRouter();

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      login(email, password),
    onSuccess: (data) => {
      // Refresh token is stored server-side in an httpOnly cookie; only the
      // access token lives in (in-memory) Zustand state.
      setAuth(data.user, data.tokens.accessToken);
      toast.success(`Welcome back, ${data.user.displayName ?? data.user.email}!`);
      router.push('/discover');
    },
    onError: () => {
      toast.error('Invalid email or password');
    },
  });
}

export function useRegister() {
  const { setAuth } = useAuthStore();
  const router = useRouter();

  return useMutation({
    mutationFn: (data: RegisterRequest) => register(data),
    onSuccess: (data) => {
      setAuth(data.user, data.tokens.accessToken);
      toast.success('Account created successfully!');
      router.push('/discover');
    },
    onError: () => {
      toast.error('Failed to create account. Email may already be in use.');
    },
  });
}

export function useLogout() {
  const { clearAuth } = useAuthStore();
  const router = useRouter();

  return useMutation({
    mutationFn: async () => {
      // The cookie is sent automatically thanks to `withCredentials: true`.
      return logout();
    },
    onSuccess: () => {
      clearAuth();
      router.push('/');
    },
    onError: () => {
      // Force logout even on error
      clearAuth();
      router.push('/');
    },
  });
}
