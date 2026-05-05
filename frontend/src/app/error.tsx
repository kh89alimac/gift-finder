'use client';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="bg-warm-50 text-warm-950">
        <div className="flex min-h-screen flex-col items-center justify-center py-16 px-4 text-center">
          <span className="text-6xl mb-6" aria-hidden="true">⚠️</span>
          <h1 className="text-2xl font-bold text-warm-950 mb-3">Something went wrong</h1>
          <p className="text-warm-500 text-sm mb-8 max-w-md">
            {error.message ?? 'An unexpected error occurred. Our team has been notified.'}
          </p>
          <button
            type="button"
            onClick={reset}
            className="rounded-full bg-gift-500 px-8 py-3 text-sm font-semibold text-white hover:bg-gift-600 transition-colors"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
