'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';
import { useItemDetail } from '../../../lib/hooks/useItemDetail';
import { formatPrice, formatDate, safeUrl } from '../../../lib/utils/format';
import TagBadge from '../../../components/gift/TagBadge';
import GiftCard from '../../../components/gift/GiftCard';

interface ItemDetailClientProps {
  id: string;
}

export default function ItemDetailClient({ id }: ItemDetailClientProps) {
  const { item, similarItems, isLoading, error } = useItemDetail(id);
  const [imageError, setImageError] = useState(false);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-10">
        <div className="flex flex-col md:flex-row gap-8">
          <div className="skeleton aspect-square w-full md:w-[420px] rounded-2xl flex-shrink-0" />
          <div className="flex-1 flex flex-col gap-4">
            <div className="skeleton h-8 rounded w-3/4" />
            <div className="skeleton h-6 rounded w-1/4" />
            <div className="skeleton h-4 rounded w-full" />
            <div className="skeleton h-4 rounded w-full" />
            <div className="skeleton h-4 rounded w-2/3" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !item) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <span className="text-5xl mb-4" aria-hidden="true">😕</span>
        <h1 className="text-xl font-semibold text-warm-900 mb-2">Item not found</h1>
        <Link href="/discover" className="text-gift-600 hover:underline text-sm">
          Back to Discover
        </Link>
      </div>
    );
  }

  const { relative, absolute } = formatDate(item.createdAt);

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="mb-6">
        <ol className="flex items-center gap-2 text-sm text-warm-500">
          <li>
            <Link href="/discover" className="hover:text-warm-700 transition-colors">Discover</Link>
          </li>
          <li aria-hidden="true">/</li>
          <li className="text-warm-900 font-medium truncate max-w-[200px]">{item.title}</li>
        </ol>
      </nav>

      {/* Main content */}
      <div className="flex flex-col md:flex-row gap-8 mb-12">
        {/* Image */}
        <div className="relative w-full md:w-[420px] flex-shrink-0 aspect-square rounded-2xl overflow-hidden bg-warm-100 shadow-sm">
          {item.imageUrl && !imageError ? (
            <Image
              src={item.imageUrl}
              alt={item.title}
              fill
              className="object-cover"
              sizes="(max-width: 768px) 100vw, 420px"
              priority
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-7xl" aria-hidden="true">
              🎁
            </div>
          )}
        </div>

        {/* Details */}
        <div className="flex-1 flex flex-col gap-4">
          <div>
            <p className="text-sm text-warm-500 font-medium mb-1">{item.retailer}</p>
            <h1 className="text-2xl sm:text-3xl font-bold text-warm-950 leading-snug">
              {item.title}
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-3xl font-bold text-gift-600">
              {formatPrice(item.price, item.currency)}
            </span>
            {item.inStock !== undefined && (
              <span className={`text-sm font-medium ${item.inStock ? 'text-green-600' : 'text-red-500'}`}>
                {item.inStock ? 'In Stock' : 'Out of Stock'}
              </span>
            )}
          </div>

          {item.description && (
            <p className="text-warm-700 leading-relaxed text-sm">{item.description}</p>
          )}

          {/* Tags */}
          {item.tags.length > 0 && (
            <div>
              <h2 className="text-sm font-medium text-warm-600 mb-2">Tags</h2>
              <div className="flex flex-wrap gap-1.5">
                {item.tags.map((tag) => (
                  <TagBadge key={tag.id} tag={tag} size="md" />
                ))}
              </div>
            </div>
          )}

          {/* Brand / SKU */}
          {(item.brand || item.sku) && (
            <div className="text-xs text-warm-400 flex gap-4">
              {item.brand && <span>Brand: {item.brand}</span>}
              {item.sku && <span>SKU: {item.sku}</span>}
            </div>
          )}

          {/* CTA */}
          <div className="flex flex-col sm:flex-row gap-3 mt-2">
            <a
              href={safeUrl(item.affiliateUrl)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-gift-500 px-8 py-3.5 text-base font-semibold text-white hover:bg-gift-600 transition-colors shadow-md shadow-gift-200"
            >
              View on {item.retailer}
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          </div>

          {/* Meta */}
          <p className="text-xs text-warm-400 mt-auto" title={absolute}>
            Added {relative}
          </p>
        </div>
      </div>

      {/* Similar items */}
      {similarItems.length > 0 && (
        <section aria-labelledby="similar-heading">
          <h2 id="similar-heading" className="text-xl font-bold text-warm-900 mb-4">
            Similar Gifts
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {similarItems.slice(0, 8).map((similar) => (
              <GiftCard key={similar.id} item={similar} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
