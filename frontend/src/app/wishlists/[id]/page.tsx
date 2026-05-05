'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';
import { toast } from 'sonner';
import {
  useWishlistDetail,
  useUpdateWishlist,
  useRemoveFromWishlist,
  useGenerateShareToken,
} from '../../../lib/hooks/useWishlists';
import { formatPrice, formatDate } from '../../../lib/utils/format';

interface PageProps {
  params: { id: string };
}

export default function WishlistDetailPage({ params }: PageProps) {
  const { id } = params;
  const { data: wishlist, isLoading, error } = useWishlistDetail(id);
  const { mutate: update } = useUpdateWishlist(id);
  const { mutate: removeItem } = useRemoveFromWishlist(id);
  const { mutate: generateShare, isPending: isGeneratingShare } = useGenerateShareToken(id);

  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState('');

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10">
        <div className="skeleton h-8 w-64 rounded mb-4" />
        <div className="skeleton h-4 w-32 rounded mb-8" />
        <div className="flex flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="skeleton h-20 rounded-xl" aria-hidden="true" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !wishlist) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <span className="text-5xl mb-4" aria-hidden="true">😕</span>
        <h1 className="text-xl font-semibold mb-2">Wishlist not found</h1>
        <Link href="/wishlists" className="text-gift-600 hover:underline text-sm">
          Back to Wishlists
        </Link>
      </div>
    );
  }

  function handleShareCopy() {
    if (wishlist?.shareToken) {
      const url = `${window.location.origin}/wishlists/shared/${wishlist.shareToken}`;
      navigator.clipboard.writeText(url);
      toast.success('Share link copied!');
    } else {
      generateShare(undefined, {
        onSuccess: (updated) => {
          const url = `${window.location.origin}/wishlists/shared/${updated.shareToken}`;
          navigator.clipboard.writeText(url);
          toast.success('Share link copied!');
        },
      });
    }
  }

  function handleSaveName() {
    if (nameValue.trim() && nameValue !== wishlist?.name) {
      update({ name: nameValue.trim() });
    }
    setEditingName(false);
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="mb-4">
        <ol className="flex items-center gap-2 text-sm text-warm-500">
          <li><Link href="/wishlists" className="hover:text-warm-700">Wishlists</Link></li>
          <li aria-hidden="true">/</li>
          <li className="text-warm-900 font-medium truncate max-w-[200px]">{wishlist.name}</li>
        </ol>
      </nav>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start gap-4 mb-8">
        <div className="flex-1">
          {editingName ? (
            <form
              onSubmit={(e) => { e.preventDefault(); handleSaveName(); }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                autoFocus
                className="text-2xl font-bold rounded-lg border border-gift-400 px-3 py-1 focus:outline-none"
                aria-label="Wishlist name"
              />
              <button type="submit" className="text-gift-600 hover:text-gift-700 text-sm font-medium">Save</button>
              <button type="button" onClick={() => setEditingName(false)} className="text-warm-400 text-sm">Cancel</button>
            </form>
          ) : (
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-warm-950">{wishlist.name}</h1>
              <button
                type="button"
                onClick={() => { setNameValue(wishlist.name); setEditingName(true); }}
                className="text-warm-400 hover:text-warm-600 transition-colors"
                aria-label="Edit wishlist name"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </button>
            </div>
          )}
          <p className="text-sm text-warm-500 mt-1">
            {wishlist.items.length} {wishlist.items.length === 1 ? 'item' : 'items'}
            {wishlist.description && ` • ${wishlist.description}`}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {/* Toggle public/private */}
          <button
            type="button"
            onClick={() => update({ isPublic: !wishlist.isPublic })}
            className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
              wishlist.isPublic
                ? 'border-green-200 bg-green-50 text-green-700 hover:bg-green-100'
                : 'border-warm-200 bg-white text-warm-700 hover:bg-warm-50'
            }`}
          >
            {wishlist.isPublic ? 'Public' : 'Private'}
          </button>

          {/* Share button */}
          <button
            type="button"
            onClick={handleShareCopy}
            disabled={isGeneratingShare}
            className="inline-flex items-center gap-2 rounded-full border border-warm-200 bg-white px-4 py-2 text-sm font-medium text-warm-700 hover:bg-warm-50 transition-colors disabled:opacity-50"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
            </svg>
            Share
          </button>
        </div>
      </div>

      {/* Items table */}
      {wishlist.items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center rounded-2xl border border-dashed border-warm-300 bg-warm-50">
          <span className="text-5xl mb-4" aria-hidden="true">🛍️</span>
          <h2 className="text-lg font-semibold text-warm-900 mb-2">No items yet</h2>
          <p className="text-warm-500 text-sm mb-4">
            Browse the discover page and add gifts to this wishlist.
          </p>
          <Link
            href="/discover"
            className="rounded-full bg-gift-500 px-5 py-2 text-sm font-semibold text-white hover:bg-gift-600 transition-colors"
          >
            Browse Gifts
          </Link>
        </div>
      ) : (
        <div className="rounded-2xl border border-warm-200 overflow-hidden">
          <table className="w-full text-sm" aria-label="Wishlist items">
            <thead className="bg-warm-50 border-b border-warm-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-warm-600 w-16 hidden sm:table-cell">Image</th>
                <th className="text-left px-4 py-3 font-medium text-warm-600">Item</th>
                <th className="text-right px-4 py-3 font-medium text-warm-600">Price</th>
                <th className="text-center px-4 py-3 font-medium text-warm-600 w-24">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-warm-100">
              {wishlist.items.map((wItem) => (
                <tr key={wItem.id} className="hover:bg-warm-50 transition-colors">
                  {/* Thumbnail */}
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <div className="relative h-12 w-12 rounded-lg overflow-hidden bg-warm-100 flex-shrink-0">
                      {wItem.item.imageUrl ? (
                        <Image
                          src={wItem.item.imageUrl}
                          alt=""
                          fill
                          className="object-cover"
                          sizes="48px"
                        />
                      ) : (
                        <span className="absolute inset-0 flex items-center justify-center text-xl" aria-hidden="true">🎁</span>
                      )}
                    </div>
                  </td>
                  {/* Title + retailer */}
                  <td className="px-4 py-3">
                    <Link
                      href={`/item/${wItem.itemId}`}
                      className="font-medium text-warm-900 hover:text-gift-600 transition-colors line-clamp-2"
                    >
                      {wItem.item.title}
                    </Link>
                    <span className="text-warm-400 text-xs">{wItem.item.retailer}</span>
                  </td>
                  {/* Price */}
                  <td className="px-4 py-3 text-right font-semibold text-gift-600">
                    {formatPrice(wItem.item.price, wItem.item.currency)}
                  </td>
                  {/* Actions */}
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-center gap-2">
                      <a
                        href={wItem.item.affiliateUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-warm-400 hover:text-gift-600 transition-colors"
                        aria-label={`Open ${wItem.item.title}`}
                      >
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      </a>
                      <button
                        type="button"
                        onClick={() => removeItem(wItem.itemId)}
                        className="text-warm-300 hover:text-blush-500 transition-colors"
                        aria-label={`Remove ${wItem.item.title}`}
                      >
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
