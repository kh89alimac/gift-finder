'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useWishlists, useCreateWishlist, useDeleteWishlist } from '../../lib/hooks/useWishlists';
import useAuthStore from '../../lib/store/authStore';
import { formatDate } from '../../lib/utils/format';

export default function WishlistsPage() {
  const { data: wishlists, isLoading } = useWishlists();
  const { mutate: createWishlist, isPending: isCreating } = useCreateWishlist();
  const { mutate: deleteWishlist } = useDeleteWishlist();
  const { user } = useAuthStore();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center px-4">
        <span className="text-5xl mb-4" aria-hidden="true">📋</span>
        <h1 className="text-2xl font-bold text-warm-900 mb-2">Sign in to view wishlists</h1>
        <p className="text-warm-600 mb-6">
          Create and share wishlists with your friends and family.
        </p>
        <Link
          href="/auth/login"
          className="rounded-full bg-gift-500 px-6 py-2.5 text-sm font-semibold text-white hover:bg-gift-600 transition-colors"
        >
          Sign in
        </Link>
      </div>
    );
  }

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    createWishlist(
      { name: newName.trim(), description: newDesc.trim() || undefined },
      {
        onSuccess: () => {
          setShowCreate(false);
          setNewName('');
          setNewDesc('');
        },
      }
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-warm-900">My Wishlists</h1>
          <p className="text-sm text-warm-500 mt-0.5">Save and share gift ideas</p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 rounded-full bg-gift-500 px-5 py-2 text-sm font-semibold text-white hover:bg-gift-600 transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Wishlist
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="mb-6 rounded-2xl border border-warm-200 bg-white p-5 shadow-sm animate-slide-up">
          <form onSubmit={handleCreate} className="flex flex-col gap-4">
            <h2 className="text-base font-semibold text-warm-900">Create New Wishlist</h2>
            <div className="flex flex-col gap-1">
              <label htmlFor="new-name" className="text-sm font-medium text-warm-700">
                Name <span className="text-blush-500">*</span>
              </label>
              <input
                id="new-name"
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Birthday Wishlist"
                required
                className="rounded-lg border border-warm-200 px-4 py-2 text-sm focus:border-gift-400 focus:outline-none"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="new-desc" className="text-sm font-medium text-warm-700">
                Description
              </label>
              <input
                id="new-desc"
                type="text"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Optional description"
                className="rounded-lg border border-warm-200 px-4 py-2 text-sm focus:border-gift-400 focus:outline-none"
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="rounded-full border border-warm-200 px-5 py-2 text-sm font-medium text-warm-700 hover:bg-warm-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isCreating || !newName.trim()}
                className="rounded-full bg-gift-500 px-5 py-2 text-sm font-semibold text-white hover:bg-gift-600 disabled:opacity-50"
              >
                {isCreating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Wishlists grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton h-36 rounded-2xl" aria-hidden="true" />
          ))}
        </div>
      ) : !wishlists?.length ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <span className="text-5xl mb-4" aria-hidden="true">📝</span>
          <h2 className="text-lg font-semibold text-warm-900 mb-2">No wishlists yet</h2>
          <p className="text-warm-500 text-sm">
            Create your first wishlist to start saving gift ideas.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {wishlists.map((list) => (
            <article
              key={list.id}
              className="group flex flex-col rounded-2xl border border-warm-200 bg-white p-5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200"
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <Link
                  href={`/wishlists/${list.id}`}
                  className="font-semibold text-warm-900 hover:text-gift-600 transition-colors line-clamp-2"
                >
                  {list.name}
                </Link>
                <span
                  className={`flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                    list.isPublic
                      ? 'bg-green-100 text-green-700'
                      : 'bg-warm-100 text-warm-600'
                  }`}
                >
                  {list.isPublic ? 'Public' : 'Private'}
                </span>
              </div>
              {list.description && (
                <p className="text-sm text-warm-500 mb-3 line-clamp-2">{list.description}</p>
              )}
              <div className="mt-auto flex items-center justify-between">
                <span className="text-sm text-warm-500">
                  {list.itemCount} {list.itemCount === 1 ? 'item' : 'items'}
                </span>
                <div className="flex items-center gap-2">
                  <Link
                    href={`/wishlists/${list.id}`}
                    className="text-sm font-medium text-gift-600 hover:text-gift-700"
                    aria-label={`View ${list.name}`}
                  >
                    View →
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      if (confirm(`Delete "${list.name}"?`)) {
                        deleteWishlist(list.id);
                      }
                    }}
                    className="text-warm-300 hover:text-blush-500 transition-colors"
                    aria-label={`Delete ${list.name}`}
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
