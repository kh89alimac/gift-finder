'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';
import { cn } from '../../lib/utils/cn';
import { formatPrice } from '../../lib/utils/format';
import type { ItemSummary } from '../../lib/types/api';
import TagBadge from './TagBadge';

interface GiftCardProps {
  item: ItemSummary;
  isWishlisted?: boolean;
  onWishlistToggle?: (itemId: string, wishlisted: boolean) => void;
  className?: string;
}

export default function GiftCard({
  item,
  isWishlisted = false,
  onWishlistToggle,
  className,
}: GiftCardProps) {
  const [imageError, setImageError] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  const displayTags = item.tags.slice(0, 3);

  return (
    <article
      className={cn(
        'group relative flex flex-col rounded-2xl bg-white border border-warm-200 overflow-hidden',
        'hover:shadow-lg hover:-translate-y-1 transition-all duration-200',
        className
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Image */}
      <div className="relative aspect-[4/3] bg-warm-100 overflow-hidden">
        {item.imageUrl && !imageError ? (
          <Image
            src={item.imageUrl}
            alt={item.title}
            fill
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            placeholder="blur"
            blurDataURL="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/+F9PQAI8wNPvd7POQAAAABJRU5ErkJggg=="
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center bg-warm-100">
            <span className="text-4xl" aria-hidden="true">🎁</span>
          </div>
        )}

        {/* Hover overlay */}
        <div
          className={cn(
            'absolute inset-0 flex items-center justify-center bg-warm-950/40 transition-opacity duration-200',
            isHovered ? 'opacity-100' : 'opacity-0'
          )}
        >
          <Link
            href={`/item/${item.id}`}
            className="rounded-full bg-white px-5 py-2 text-sm font-semibold text-warm-900 hover:bg-warm-100 transition-colors"
            aria-label={`View ${item.title}`}
          >
            View Gift
          </Link>
        </div>

        {/* Wishlist button */}
        {onWishlistToggle && (
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              onWishlistToggle(item.id, !isWishlisted);
            }}
            className={cn(
              'absolute top-2 right-2 flex h-8 w-8 items-center justify-center rounded-full',
              'bg-white/90 shadow-sm hover:scale-110 transition-all duration-150',
              'focus-visible:outline-2 focus-visible:outline-gift-500'
            )}
            aria-label={isWishlisted ? 'Remove from wishlist' : 'Add to wishlist'}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill={isWishlisted ? 'currentColor' : 'none'}
              stroke="currentColor"
              strokeWidth={2}
              className={cn(
                'h-4 w-4 transition-colors',
                isWishlisted ? 'text-blush-500' : 'text-warm-400 hover:text-blush-400'
              )}
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z"
              />
            </svg>
          </button>
        )}

        {/* Retailer badge */}
        <div className="absolute bottom-2 left-2">
          <span className="rounded-md bg-white/90 px-2 py-0.5 text-xs font-medium text-warm-600 shadow-sm">
            {item.retailer}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-col gap-2 p-4">
        {/* Title */}
        <Link href={`/item/${item.id}`} className="hover:text-gift-600 transition-colors">
          <h3
            className="font-semibold text-warm-900 text-sm leading-snug line-clamp-2"
            title={item.title}
          >
            {item.title}
          </h3>
        </Link>

        {/* Price */}
        <p className="text-gift-600 font-bold text-base">
          {formatPrice(item.price, item.currency)}
        </p>

        {/* Tags */}
        {displayTags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {displayTags.map((tag) => (
              <TagBadge key={tag.id} tag={tag} />
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
