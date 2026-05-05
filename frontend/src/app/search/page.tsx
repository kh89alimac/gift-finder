'use client';

import { useState, useRef } from 'react';
import { useAISearch } from '../../lib/hooks/useAISearch';
import GiftCard from '../../components/gift/GiftCard';

const EXAMPLE_QUERIES = [
  'A birthday gift for my mom who loves gardening, under $50',
  'Tech gadget for a college student under $75',
  'Romantic anniversary gift for my partner who loves cooking',
  'Christmas present for a 10-year-old who loves dinosaurs',
  'Practical gift for a new homeowner under $100',
  'Self-care gift for a friend going through a tough time',
];

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const { search, result, isPending, isError } = useAISearch();
  const inputRef = useRef<HTMLTextAreaElement>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    search({ query: q });
  }

  function handleExampleClick(example: string) {
    setQuery(example);
    inputRef.current?.focus();
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      {/* Hero input */}
      <div className="text-center mb-8">
        <h1 className="text-3xl sm:text-4xl font-bold text-warm-950 mb-3">
          AI Gift Search
        </h1>
        <p className="text-warm-600 max-w-xl mx-auto">
          Describe who you&apos;re shopping for in plain English and let AI find the perfect match.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mb-8">
        <div className="relative rounded-2xl border border-warm-200 bg-white shadow-sm focus-within:border-gift-400 focus-within:ring-1 focus-within:ring-gift-400 transition-shadow">
          <textarea
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e as unknown as React.FormEvent);
              }
            }}
            placeholder="e.g. A birthday gift for my mom who loves gardening, under $50"
            rows={3}
            className="w-full resize-none rounded-2xl bg-transparent px-5 py-4 pr-24 text-base text-warm-900 placeholder:text-warm-400 focus:outline-none"
            aria-label="Search query"
            disabled={isPending}
          />
          <button
            type="submit"
            disabled={isPending || !query.trim()}
            className="absolute bottom-3 right-3 inline-flex items-center gap-1.5 rounded-full bg-gift-500 px-5 py-2 text-sm font-semibold text-white hover:bg-gift-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            aria-label="Search for gifts"
          >
            {isPending ? (
              <>
                <div className="h-3.5 w-3.5 rounded-full border-2 border-white/50 border-t-white animate-spin" />
                Searching…
              </>
            ) : (
              <>
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
                Search
              </>
            )}
          </button>
        </div>
        <p className="mt-2 text-xs text-warm-400 text-right">
          Press Enter to search, Shift+Enter for new line
        </p>
      </form>

      {/* Example chips (shown when no result yet) */}
      {!result && !isPending && (
        <div className="mb-10">
          <p className="text-sm font-medium text-warm-600 mb-3">Try an example:</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => handleExampleClick(example)}
                className="rounded-full border border-warm-200 bg-white px-4 py-2 text-xs text-warm-600 hover:bg-warm-50 hover:border-gift-300 transition-colors"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="rounded-xl border border-blush-200 bg-blush-50 px-5 py-4 mb-8">
          <p className="text-sm text-blush-700">
            Something went wrong with the AI search. Please try again.
          </p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="flex flex-col gap-8 animate-fade-in">
          {/* AI interpretation */}
          <div className="rounded-2xl border border-gift-200 bg-gift-50 px-6 py-5">
            <div className="flex items-start gap-3">
              <span className="text-2xl mt-0.5" aria-hidden="true">✨</span>
              <div>
                <h2 className="text-sm font-semibold text-gift-800 mb-1">AI Interpretation</h2>
                <p className="text-sm text-gift-700">{result.interpretation}</p>
              </div>
            </div>
          </div>

          {/* Suggestions */}
          {result.suggestions.length > 0 && (
            <div>
              <p className="text-sm font-medium text-warm-600 mb-2">Refine your search:</p>
              <div className="flex flex-wrap gap-2">
                {result.suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => {
                      setQuery(suggestion);
                      search({ query: suggestion });
                    }}
                    className="rounded-full border border-warm-200 bg-white px-4 py-1.5 text-xs text-warm-600 hover:bg-warm-50 hover:border-gift-300 transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Result count */}
          <div>
            <h2 className="text-lg font-semibold text-warm-900 mb-4">
              {result.results.length} gifts found
            </h2>
            {result.results.length === 0 ? (
              <div className="text-center py-12 text-warm-500">
                <span className="text-4xl block mb-3" aria-hidden="true">🔍</span>
                <p>No matching gifts found. Try a different description.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {result.results.map(({ item, explanation }) => (
                  <div key={item.id} className="flex flex-col gap-2">
                    <GiftCard item={item} />
                    {explanation && (
                      <p className="text-xs text-warm-500 px-1">{explanation}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
