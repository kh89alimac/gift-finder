'use client';

import useFilterStore from '../../lib/store/filterStore';
import { cn } from '../../lib/utils/cn';

export default function ActiveFilters({ className }: { className?: string }) {
  const {
    ageMin, ageMax, relationship, occasion, interests,
    budgetMin, budgetMax, sort,
    setFilter, resetFilters, hasActiveFilters,
  } = useFilterStore();

  if (!hasActiveFilters()) return null;

  const chips: { label: string; onRemove: () => void }[] = [];

  if (relationship) {
    chips.push({
      label: `Relationship: ${relationship}`,
      onRemove: () => setFilter('relationship', null),
    });
  }

  if (ageMin !== null || ageMax !== null) {
    const label =
      ageMin !== null && ageMax !== null
        ? `Age: ${ageMin}–${ageMax}`
        : ageMin !== null
        ? `Age: ${ageMin}+`
        : `Age: up to ${ageMax}`;
    chips.push({
      label,
      onRemove: () => {
        setFilter('ageMin', null);
        setFilter('ageMax', null);
      },
    });
  }

  occasion.forEach((occ) => {
    chips.push({
      label: `Occasion: ${occ}`,
      onRemove: () => setFilter('occasion', occasion.filter((o) => o !== occ)),
    });
  });

  interests.forEach((interest) => {
    chips.push({
      label: `Interest: ${interest}`,
      onRemove: () => setFilter('interests', interests.filter((i) => i !== interest)),
    });
  });

  if (budgetMin !== null || budgetMax !== null) {
    const label =
      budgetMin !== null && budgetMax !== null
        ? `$${budgetMin}–$${budgetMax}`
        : budgetMin !== null
        ? `Over $${budgetMin}`
        : `Under $${budgetMax}`;
    chips.push({
      label,
      onRemove: () => {
        setFilter('budgetMin', null);
        setFilter('budgetMax', null);
      },
    });
  }

  if (sort !== 'relevance') {
    chips.push({
      label: `Sort: ${sort.replace('_', ' ')}`,
      onRemove: () => setFilter('sort', 'relevance'),
    });
  }

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)} aria-label="Active filters">
      <span className="text-xs font-medium text-warm-500">Active:</span>
      {chips.map((chip) => (
        <span
          key={chip.label}
          className="inline-flex items-center gap-1 rounded-full bg-gift-100 border border-gift-200 px-2.5 py-1 text-xs font-medium text-gift-700"
        >
          {chip.label}
          <button
            type="button"
            onClick={chip.onRemove}
            className="ml-0.5 hover:text-gift-900 transition-colors"
            aria-label={`Remove filter: ${chip.label}`}
          >
            <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </span>
      ))}
      <button
        type="button"
        onClick={resetFilters}
        className="text-xs font-medium text-warm-500 hover:text-warm-700 underline transition-colors"
      >
        Clear all
      </button>
    </div>
  );
}
