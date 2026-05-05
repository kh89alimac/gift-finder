'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import { cn } from '../../lib/utils/cn';
import useAuthStore from '../../lib/store/authStore';
import { useLogout } from '../../lib/hooks/useAuth';

const navLinks = [
  { href: '/discover', label: 'Discover' },
  { href: '/search', label: 'AI Search' },
  { href: '/wishlists', label: 'Wishlists' },
];

export default function Header() {
  const pathname = usePathname();
  const { user, isAdmin } = useAuthStore();
  const { mutate: logout } = useLogout();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-warm-200 bg-white/95 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 gap-4">
        {/* Logo */}
        <Link
          href="/"
          className="flex items-center gap-2 font-bold text-xl text-gift-600 flex-shrink-0"
          aria-label="Gift Finder home"
        >
          <span aria-hidden="true">🎁</span>
          <span>Gift Finder</span>
        </Link>

        {/* Desktop nav */}
        <nav
          className="hidden md:flex items-center gap-1"
          aria-label="Main navigation"
        >
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                'rounded-full px-4 py-2 text-sm font-medium transition-colors',
                pathname.startsWith(link.href)
                  ? 'bg-gift-100 text-gift-700'
                  : 'text-warm-600 hover:text-warm-900 hover:bg-warm-100'
              )}
            >
              {link.label}
            </Link>
          ))}
          {isAdmin() && (
            <Link
              href="/admin"
              className={cn(
                'rounded-full px-4 py-2 text-sm font-medium transition-colors',
                pathname.startsWith('/admin')
                  ? 'bg-warm-900 text-white'
                  : 'text-warm-600 hover:text-warm-900 hover:bg-warm-100'
              )}
            >
              Admin
            </Link>
          )}
        </nav>

        {/* Auth area */}
        <div className="hidden md:flex items-center gap-2">
          {user ? (
            <div className="relative">
              <button
                type="button"
                onClick={() => setProfileOpen((v) => !v)}
                className="flex items-center gap-2 rounded-full bg-warm-100 px-3 py-2 text-sm font-medium text-warm-700 hover:bg-warm-200 transition-colors"
                aria-expanded={profileOpen}
                aria-haspopup="menu"
                aria-label="User menu"
              >
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-gift-500 text-white text-xs font-bold">
                  {(user.displayName ?? user.email).charAt(0).toUpperCase()}
                </div>
                <span className="max-w-[120px] truncate">
                  {user.displayName ?? user.email.split('@')[0]}
                </span>
              </button>

              {profileOpen && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setProfileOpen(false)}
                    aria-hidden="true"
                  />
                  <div
                    className="absolute right-0 top-full mt-1 z-20 min-w-[160px] rounded-xl border border-warm-200 bg-white shadow-lg py-1"
                    role="menu"
                    aria-label="User menu"
                  >
                    <Link
                      href="/wishlists"
                      className="block px-4 py-2 text-sm text-warm-700 hover:bg-warm-50"
                      role="menuitem"
                      onClick={() => setProfileOpen(false)}
                    >
                      My Wishlists
                    </Link>
                    {isAdmin() && (
                      <Link
                        href="/admin"
                        className="block px-4 py-2 text-sm text-warm-700 hover:bg-warm-50"
                        role="menuitem"
                        onClick={() => setProfileOpen(false)}
                      >
                        Admin Panel
                      </Link>
                    )}
                    <hr className="my-1 border-warm-100" />
                    <button
                      type="button"
                      onClick={() => {
                        setProfileOpen(false);
                        logout();
                      }}
                      className="block w-full text-left px-4 py-2 text-sm text-blush-600 hover:bg-blush-50"
                      role="menuitem"
                    >
                      Sign out
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <>
              <Link
                href="/auth/login"
                className="rounded-full px-4 py-2 text-sm font-medium text-warm-700 hover:bg-warm-100 transition-colors"
              >
                Log in
              </Link>
              <Link
                href="/auth/register"
                className="rounded-full bg-gift-500 px-4 py-2 text-sm font-medium text-white hover:bg-gift-600 transition-colors"
              >
                Sign up
              </Link>
            </>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          type="button"
          className="md:hidden flex items-center justify-center h-8 w-8 rounded-full hover:bg-warm-100 transition-colors"
          onClick={() => setMobileOpen((v) => !v)}
          aria-expanded={mobileOpen}
          aria-label="Toggle mobile menu"
        >
          <svg
            className="h-5 w-5 text-warm-700"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            {mobileOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-warm-100 bg-white px-4 py-4 flex flex-col gap-1">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setMobileOpen(false)}
              className={cn(
                'rounded-xl px-4 py-2.5 text-sm font-medium transition-colors',
                pathname.startsWith(link.href)
                  ? 'bg-gift-100 text-gift-700'
                  : 'text-warm-700 hover:bg-warm-100'
              )}
            >
              {link.label}
            </Link>
          ))}
          {isAdmin() && (
            <Link
              href="/admin"
              onClick={() => setMobileOpen(false)}
              className="rounded-xl px-4 py-2.5 text-sm font-medium text-warm-700 hover:bg-warm-100"
            >
              Admin
            </Link>
          )}
          <hr className="my-2 border-warm-100" />
          {user ? (
            <button
              type="button"
              onClick={() => {
                setMobileOpen(false);
                logout();
              }}
              className="rounded-xl px-4 py-2.5 text-sm font-medium text-blush-600 hover:bg-blush-50 text-left"
            >
              Sign out
            </button>
          ) : (
            <div className="flex gap-2">
              <Link
                href="/auth/login"
                onClick={() => setMobileOpen(false)}
                className="flex-1 rounded-full border border-warm-200 py-2 text-center text-sm font-medium text-warm-700 hover:bg-warm-100"
              >
                Log in
              </Link>
              <Link
                href="/auth/register"
                onClick={() => setMobileOpen(false)}
                className="flex-1 rounded-full bg-gift-500 py-2 text-center text-sm font-medium text-white hover:bg-gift-600"
              >
                Sign up
              </Link>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
