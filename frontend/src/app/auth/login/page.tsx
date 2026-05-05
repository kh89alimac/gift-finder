'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useLogin } from '../../../lib/hooks/useAuth';

export default function LoginPage() {
  const { mutate: login, isPending, isError } = useLogin();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});

  function validate(): boolean {
    const next: typeof errors = {};
    if (!email.trim()) next.email = 'Email is required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) next.email = 'Enter a valid email';
    if (!password) next.password = 'Password is required';
    else if (password.length < 6) next.password = 'Password must be at least 6 characters';
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    login({ email, password });
  }

  return (
    <div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-4xl mb-3" aria-hidden="true">🎁</div>
          <h1 className="text-2xl font-bold text-warm-950">Welcome back</h1>
          <p className="text-warm-500 text-sm mt-1">Sign in to your Gift Finder account</p>
        </div>

        <div className="rounded-2xl border border-warm-200 bg-white p-7 shadow-sm">
          <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
            {/* Email */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="email" className="text-sm font-medium text-warm-700">
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setErrors((p) => ({ ...p, email: undefined })); }}
                className={`rounded-lg border px-4 py-2.5 text-sm focus:outline-none focus:ring-1 ${
                  errors.email
                    ? 'border-blush-400 focus:border-blush-400 focus:ring-blush-400'
                    : 'border-warm-200 focus:border-gift-400 focus:ring-gift-400'
                }`}
                aria-describedby={errors.email ? 'email-error' : undefined}
                aria-invalid={Boolean(errors.email)}
              />
              {errors.email && (
                <p id="email-error" className="text-xs text-blush-600" role="alert">
                  {errors.email}
                </p>
              )}
            </div>

            {/* Password */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="password" className="text-sm font-medium text-warm-700">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setErrors((p) => ({ ...p, password: undefined })); }}
                className={`rounded-lg border px-4 py-2.5 text-sm focus:outline-none focus:ring-1 ${
                  errors.password
                    ? 'border-blush-400 focus:border-blush-400 focus:ring-blush-400'
                    : 'border-warm-200 focus:border-gift-400 focus:ring-gift-400'
                }`}
                aria-describedby={errors.password ? 'password-error' : undefined}
                aria-invalid={Boolean(errors.password)}
              />
              {errors.password && (
                <p id="password-error" className="text-xs text-blush-600" role="alert">
                  {errors.password}
                </p>
              )}
            </div>

            {/* Server error */}
            {isError && (
              <div
                className="rounded-lg border border-blush-200 bg-blush-50 px-4 py-3 text-sm text-blush-700"
                role="alert"
              >
                Invalid email or password. Please try again.
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isPending}
              className="rounded-full bg-gift-500 py-3 text-sm font-semibold text-white hover:bg-gift-600 disabled:opacity-50 transition-colors"
            >
              {isPending ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="text-center text-sm text-warm-500 mt-6">
          Don&apos;t have an account?{' '}
          <Link href="/auth/register" className="font-medium text-gift-600 hover:text-gift-700">
            Sign up free
          </Link>
        </p>
      </div>
    </div>
  );
}
