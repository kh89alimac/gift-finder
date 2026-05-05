'use client';

import { useState, useCallback } from 'react';
import { cn } from '../../lib/utils/cn';
import useFilterStore from '../../lib/store/filterStore';

const RELATIONSHIPS = [
  'Mom', 'Dad', 'Partner', 'Friend', 'Sibling', 'Child',
  'Grandparent', 'Colleague', 'Boss', 'Mentor',
];

const OCCASIONS = [
  'Birthday', 'Anniversary', 'Christmas', 'Valentine\'s Day',
  'Mother\'s Day', 'Father\'s Day', 'Graduation', 'Wedding',
  'Housewarming', 'Thank You', 'Just Because',
];

const INTERESTS = [
  'Tech', 'Cooking', 'Fitness', 'Reading', 'Gaming', 'Travel',
  'Music', 'Art', 'Gardening', 'Fashion', 'Sports', 'DIY',
  'Movies', 'Pets', 'Coffee', 'Wine', 'Yoga', 'Photography',
];

const SORT_OPTIONS = [
  { value: 'relevance', label: 'Most Relevant' },
  { value: 'price_asc', label: 'Price: Low to High' },
  { value: 'price_desc', label: 'Price: High to Low' },
  { value: 'newest', label: 'Newest First' },
  { value: 'popular', label: 'Most Popular' },
] as const;

interface FilterPanelProps {
  onClose?: () => void;
  isMobile?: boolean;
}

export default function FilterPanel({ onClose, isMobile = false }: FilterPanelProps) {
  const {
    ageMin, ageMax, relationship, occasion, interests,
    budgetMin, budgetMax, sort,
    setFilter, resetFilters,
  } = useFilterStore();

  const [interestSearch, setInterestSearch] = useState('');

  const filteredInterests = INTERESTS.filter((i) =>
    i.toLowerCase().includes(interestSearch.toLowerCase())
  );

  const toggleOccasion = useCallback(
    (occ: string) => {
      const next = occasion.includes(occ)
        ? occasion.filter((o) => o !== occ)
        : [...occasion, occ];
      setFilter('occasion', next);
    },
    [occasion, setFilter]
  );

  const toggleInterest = useCallback(
    (interest: string) => {
      const next = interests.includes(interest)
        ? interests.filter((i) => i !== interest)
        : [...interests, interest];
      setFilter('interests', next);
    },
    [interests, setFilter]
  );

  return (
    <aside
      className={cn(
        'flex flex-col gap-6 bg-white rounded-2xl border border-warm-200 p-5',
        isMobile ? 'rounded-none border-0 p-4' : ''
      )}
      aria-label="Gift filters"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-warm-900">Filters</h2>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={resetFilters}
            className="text-xs text-gift-600 hover:text-gift-700 font-medium transition-colors"
          >
            Reset all
          </button>
          {isMobile && onClose && (
            <button
              type="button"
              onClick={onClose}
              className="ml-2 text-warm-400 hover:text-warm-600 transition-colors"
              aria-label="Close filters"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Sort */}
      <section>
        <h3 className="text-sm font-medium text-warm-700 mb-2">Sort by</h3>
        <select
          value={sort}
          onChange={(e) => setFilter('sort', e.target.value as typeof sort)}
          className="w-full rounded-lg border border-warm-200 bg-white px-3 py-2 text-sm text-warm-900 focus:border-gift-400 focus:outline-none"
          aria-label="Sort results"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </section>

      {/* Recipient */}
      <section>
        <h3 className="text-sm font-medium text-warm-700 mb-2">Recipient</h3>
        <div className="flex flex-col gap-3">
          {/* Relationship */}
          <div>
            <label className="text-xs text-warm-500 mb-1 block">Relationship</label>
            <div className="flex flex-wrap gap-1.5">
              {RELATIONSHIPS.map((rel) => (
                <button
                  key={rel}
                  type="button"
                  onClick={() => setFilter('relationship', relationship === rel.toLowerCase() ? null : rel.toLowerCase())}
                  className={cn(
                    'rounded-full px-3 py-1 text-xs font-medium border transition-colors',
                    relationship === rel.toLowerCase()
                      ? 'bg-gift-500 text-white border-gift-500'
                      : 'bg-white text-warm-700 border-warm-200 hover:border-gift-300'
                  )}
                  aria-pressed={relationship === rel.toLowerCase()}
                >
                  {rel}
                </button>
              ))}
            </div>
          </div>

          {/* Age Range */}
          <div>
            <label className="text-xs text-warm-500 mb-1 block">Age range</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                placeholder="Min"
                min={0}
                max={120}
                value={ageMin ?? ''}
                onChange={(e) => setFilter('ageMin', e.target.value ? Number(e.target.value) : null)}
                className="w-full rounded-lg border border-warm-200 px-3 py-2 text-sm focus:border-gift-400 focus:outline-none"
                aria-label="Minimum age"
              />
              <span className="text-warm-400 text-sm">to</span>
              <input
                type="number"
                placeholder="Max"
                min={0}
                max={120}
                value={ageMax ?? ''}
                onChange={(e) => setFilter('ageMax', e.target.value ? Number(e.target.value) : null)}
                className="w-full rounded-lg border border-warm-200 px-3 py-2 text-sm focus:border-gift-400 focus:outline-none"
                aria-label="Maximum age"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Occasion */}
      <section>
        <h3 className="text-sm font-medium text-warm-700 mb-2">Occasion</h3>
        <div className="flex flex-wrap gap-1.5">
          {OCCASIONS.map((occ) => (
            <button
              key={occ}
              type="button"
              onClick={() => toggleOccasion(occ.toLowerCase())}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium border transition-colors',
                occasion.includes(occ.toLowerCase())
                  ? 'bg-blue-500 text-white border-blue-500'
                  : 'bg-white text-warm-700 border-warm-200 hover:border-blue-300'
              )}
              aria-pressed={occasion.includes(occ.toLowerCase())}
            >
              {occ}
            </button>
          ))}
        </div>
      </section>

      {/* Interests */}
      <section>
        <h3 className="text-sm font-medium text-warm-700 mb-2">Interests</h3>
        <input
          type="search"
          placeholder="Search interests…"
          value={interestSearch}
          onChange={(e) => setInterestSearch(e.target.value)}
          className="mb-2 w-full rounded-lg border border-warm-200 px-3 py-1.5 text-sm focus:border-gift-400 focus:outline-none"
          aria-label="Search interests"
        />
        <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
          {filteredInterests.map((interest) => (
            <button
              key={interest}
              type="button"
              onClick={() => toggleInterest(interest.toLowerCase())}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium border transition-colors',
                interests.includes(interest.toLowerCase())
                  ? 'bg-green-500 text-white border-green-500'
                  : 'bg-white text-warm-700 border-warm-200 hover:border-green-300'
              )}
              aria-pressed={interests.includes(interest.toLowerCase())}
            >
              {interest}
            </button>
          ))}
        </div>
      </section>

      {/* Budget */}
      <section>
        <h3 className="text-sm font-medium text-warm-700 mb-2">Budget</h3>
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-warm-400 text-sm">$</span>
            <input
              type="number"
              placeholder="Min"
              min={0}
              value={budgetMin ?? ''}
              onChange={(e) => setFilter('budgetMin', e.target.value ? Number(e.target.value) : null)}
              className="w-full rounded-lg border border-warm-200 pl-7 pr-3 py-2 text-sm focus:border-gift-400 focus:outline-none"
              aria-label="Minimum budget"
            />
          </div>
          <span className="text-warm-400 text-sm">to</span>
          <div className="relative flex-1">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-warm-400 text-sm">$</span>
            <input
              type="number"
              placeholder="Max"
              min={0}
              value={budgetMax ?? ''}
              onChange={(e) => setFilter('budgetMax', e.target.value ? Number(e.target.value) : null)}
              className="w-full rounded-lg border border-warm-200 pl-7 pr-3 py-2 text-sm focus:border-gift-400 focus:outline-none"
              aria-label="Maximum budget"
            />
          </div>
        </div>
        {/* Quick budget presets */}
        <div className="flex flex-wrap gap-1.5 mt-2">
          {[
            { label: 'Under $25', max: 25 },
            { label: 'Under $50', max: 50 },
            { label: 'Under $100', max: 100 },
            { label: 'Under $200', max: 200 },
          ].map((preset) => (
            <button
              key={preset.max}
              type="button"
              onClick={() => {
                setFilter('budgetMin', null);
                setFilter('budgetMax', preset.max);
              }}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium border transition-colors',
                budgetMax === preset.max && budgetMin === null
                  ? 'bg-yellow-400 text-yellow-900 border-yellow-400'
                  : 'bg-white text-warm-700 border-warm-200 hover:border-yellow-300'
              )}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </section>

      {isMobile && (
        <button
          type="button"
          onClick={onClose}
          className="mt-2 w-full rounded-full bg-gift-500 py-3 text-sm font-semibold text-white hover:bg-gift-600 transition-colors"
        >
          Apply Filters
        </button>
      )}
    </aside>
  );
}
