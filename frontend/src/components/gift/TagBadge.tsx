'use client';

import { cn } from '../../lib/utils/cn';
import type { TagSlim, TagType } from '../../lib/types/api';

const tagTypeStyles: Record<TagType, string> = {
  occasion: 'bg-blue-100 text-blue-700 border-blue-200 hover:bg-blue-200',
  interest: 'bg-green-100 text-green-700 border-green-200 hover:bg-green-200',
  recipient: 'bg-purple-100 text-purple-700 border-purple-200 hover:bg-purple-200',
  price: 'bg-yellow-100 text-yellow-700 border-yellow-200 hover:bg-yellow-200',
  theme: 'bg-gift-100 text-gift-700 border-gift-200 hover:bg-gift-200',
  other: 'bg-warm-100 text-warm-700 border-warm-200 hover:bg-warm-200',
};

interface TagBadgeProps {
  tag: TagSlim;
  onClick?: (tag: TagSlim) => void;
  size?: 'sm' | 'md';
  className?: string;
}

export default function TagBadge({ tag, onClick, size = 'sm', className }: TagBadgeProps) {
  const sizeStyles = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
  const styles = tagTypeStyles[tag.type] ?? tagTypeStyles.other;

  if (onClick) {
    return (
      <button
        type="button"
        onClick={() => onClick(tag)}
        className={cn(
          'inline-flex items-center rounded-full border font-medium transition-colors cursor-pointer',
          sizeStyles,
          styles,
          className
        )}
        aria-label={`Filter by ${tag.name}`}
      >
        {tag.name}
      </button>
    );
  }

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border font-medium',
        sizeStyles,
        styles,
        className
      )}
    >
      {tag.name}
    </span>
  );
}
