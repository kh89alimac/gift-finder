export default function RootLoading() {
  return (
    <div className="flex min-h-[calc(100vh-64px)] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-10 w-10 rounded-full border-4 border-gift-200 border-t-gift-500 animate-spin" />
        <p className="text-sm text-warm-500">Loading…</p>
      </div>
    </div>
  );
}
