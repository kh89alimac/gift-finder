'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useRegister } from '../../../lib/hooks/useAuth';

export default function RegisterPage() {
  const { mutate: register, isPending, isError } = useRegister();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [errors, setErrors] = useState<{ email?: string; password?: string; displayName?: string }>({});

  function validate(): boolean {
    const next: typeof errors = {};
    if (!email.trim()) next.email = 'Email is required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) next.email = 'Enter a valid email';
    if (!password) next.password = 'Password is required';
    else if (password.length < 8) next.password = 'Password must be at least 8 characters';
    else if (!/[A-Z]/.test(password) && !/[0-9]/.test(password)) {
      next.password = 'Password must contain a number or capital letter';
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    register({
      email,
      password,
      displayName: displayName.trim() || undefined,
    });
  }

  return (
    <div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-4xl mb-3" aria-hidden="true">🎁</div>
          <h1 className="text-2xl font-bold text-warm-950">Create an account</h1>
          <p className="text-warm-500 text-sm mt-1">Start finding perfect gifts today</p>
        </div>

        <div className="rounded-2xl border border-warm-200 bg-white p-7 shadow-sm">
          <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
            {/* Display name */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="displayName" className="text-sm font-medium text-warm-700">
                Your name <span className="text-warm-400 font-normal">(optional)</span>
              </label>
              <input
                id="displayName"
                type="text"
                autoComplete="name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. Alex"
                className="rounded-lg border border-warm-200 px-4 py-2.5 text-sm focus:border-gift-400 focus:outline-none focus:ring-1 focus:ring-gift-400"
              />
            </div>

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
                autoComplete="new-password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setErrors((p) => ({ ...p, password: undefined })); }}
                className={`rounded-lg border px-4 py-2.5 text-sm focus:outline-none focus:ring-1 ${
                  errors.password
                    ? 'border-blush-400 focus:border-blush-400 focus:ring-blush-400'
                    : 'border-warm-200 focus:border-gift-400 focus:ring-gift-400'
                }`}
                aria-describedby="password-hint password-error"
                aria-invalid={Boolean(errors.password)}
              />
              <p id="password-hint" className="text-xs text-warm-400">
                At least 8 characters with a number or capital letter
              </p>
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
                Could not create account. That email may already be registered.
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isPending}
              className="rounded-full bg-gift-500 py-3 text-sm font-semibold text-white hover:bg-gift-600 disabled:opacity-50 transition-colors"
            >
              {isPending ? 'Creating account…' : 'Create account'}
            </button>

            <p className="text-center text-xs text-warm-400">
              By creating an account you agree to our{' '}
              <span className="underline cursor-pointer">Terms of Service</span> and{' '}
              <span className="underline cursor-pointer">Privacy Policy</span>.
            </p>
          </form>
        </div>

        <p className="text-center text-sm text-warm-500 mt-6">
          Already have an account?{' '}
          <Link href="/auth/login" className="font-medium text-gift-600 hover:text-gift-700">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
