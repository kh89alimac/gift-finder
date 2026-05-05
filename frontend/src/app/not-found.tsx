import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: '404 — Page Not Found',
};

export default function NotFound() {
  return (
    <div className="flex min-h-[calc(100vh-64px)] flex-col items-center justify-center py-16 px-4 text-center">
      <span className="text-6xl mb-6" aria-hidden="true">🎁</span>
      <h1 className="text-4xl font-bold text-warm-950 mb-3">404</h1>
      <h2 className="text-xl font-semibold text-warm-700 mb-4">Page not found</h2>
      <p className="text-warm-500 text-sm mb-8 max-w-sm">
        This gift unwrapped to nothing. The page you&apos;re looking for doesn&apos;t exist or has been moved.
      </p>
      <Link
        href="/discover"
        className="rounded-full bg-gift-500 px-8 py-3 text-sm font-semibold text-white hover:bg-gift-600 transition-colors"
      >
        Discover Gifts
      </Link>
    </div>
  );
}
