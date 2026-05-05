export default function DiscoverLoading() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Header skeleton */}
      <div className="mb-6">
        <div className="skeleton h-8 w-48 rounded mb-2" />
        <div className="skeleton h-4 w-64 rounded" />
      </div>

      <div className="flex gap-6">
        {/* Filter panel skeleton */}
        <aside className="hidden md:block w-64 flex-shrink-0">
          <div className="rounded-2xl border border-warm-200 bg-white p-5 flex flex-col gap-4">
            <div className="skeleton h-5 w-20 rounded" />
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex flex-col gap-2">
                <div className="skeleton h-4 w-24 rounded" />
                <div className="flex flex-wrap gap-1.5">
                  {Array.from({ length: 4 }).map((_, j) => (
                    <div key={j} className="skeleton h-7 w-16 rounded-full" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </aside>

        {/* Grid skeleton */}
        <div className="flex-1 min-w-0">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 12 }).map((_, i) => (
              <div
                key={i}
                className="rounded-2xl border border-warm-200 overflow-hidden bg-white"
                aria-hidden="true"
              >
                <div className="aspect-[4/3] skeleton" />
                <div className="p-4 flex flex-col gap-2">
                  <div className="skeleton h-4 rounded w-full" />
                  <div className="skeleton h-4 rounded w-3/4" />
                  <div className="skeleton h-5 rounded w-1/3" />
                  <div className="flex gap-1">
                    <div className="skeleton h-5 rounded-full w-16" />
                    <div className="skeleton h-5 rounded-full w-12" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
