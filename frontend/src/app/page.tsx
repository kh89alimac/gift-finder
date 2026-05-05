import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Find the Perfect Gift',
  description: 'Discover personalized gift ideas for every occasion, budget, and relationship.',
};

const quickStartCards = [
  {
    label: 'For your mom',
    occasion: 'Birthday',
    budget: 'Under $50',
    href: '/discover?relationship=mom&occasion=birthday&budgetMax=50',
    emoji: '🌸',
    bg: 'from-pink-100 to-rose-50',
  },
  {
    label: 'For your partner',
    occasion: 'Anniversary',
    budget: '$50–$150',
    href: '/discover?relationship=partner&occasion=anniversary&budgetMin=50&budgetMax=150',
    emoji: '❤️',
    bg: 'from-red-100 to-rose-50',
  },
  {
    label: 'For a friend',
    occasion: 'Just because',
    budget: 'Under $30',
    href: '/discover?relationship=friend&budgetMax=30',
    emoji: '🎁',
    bg: 'from-orange-100 to-amber-50',
  },
  {
    label: 'For your dad',
    occasion: "Father's Day",
    budget: 'Under $75',
    href: "/discover?relationship=dad&occasion=father's-day&budgetMax=75",
    emoji: '🛠️',
    bg: 'from-amber-100 to-yellow-50',
  },
  {
    label: 'For a colleague',
    occasion: 'Work milestone',
    budget: 'Under $25',
    href: '/discover?relationship=colleague&budgetMax=25',
    emoji: '💼',
    bg: 'from-blue-100 to-sky-50',
  },
  {
    label: 'For your kid',
    occasion: 'Birthday',
    budget: 'Under $40',
    href: '/discover?relationship=child&occasion=birthday&budgetMax=40',
    emoji: '🧸',
    bg: 'from-purple-100 to-violet-50',
  },
];

export default function HomePage() {
  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-gift-50 via-warm-100 to-blush-50 px-4 py-20 sm:py-32 text-center">
        <div className="absolute inset-0 opacity-10 pointer-events-none"
          style={{
            backgroundImage: 'radial-gradient(circle at 20% 50%, #e8903a 0%, transparent 50%), radial-gradient(circle at 80% 20%, #f05252 0%, transparent 50%)',
          }}
        />
        <div className="relative mx-auto max-w-3xl">
          <span className="inline-block mb-4 rounded-full bg-gift-100 px-4 py-1.5 text-sm font-medium text-gift-700">
            AI-Powered Gift Discovery
          </span>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-warm-950 mb-6 leading-tight">
            Find the{' '}
            <span className="text-gift-500">perfect gift</span>
            <br />
            for anyone
          </h1>
          <p className="text-lg sm:text-xl text-warm-700 mb-10 max-w-xl mx-auto">
            Tell us about who you&apos;re shopping for — age, interests, occasion, budget —
            and we&apos;ll surface gifts they&apos;ll actually love.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/discover"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-gift-500 px-8 py-3.5 text-base font-semibold text-white hover:bg-gift-600 transition-colors shadow-lg shadow-gift-200"
            >
              Browse Gifts
            </Link>
            <Link
              href="/search"
              className="inline-flex items-center justify-center gap-2 rounded-full border-2 border-gift-300 bg-white px-8 py-3.5 text-base font-semibold text-gift-700 hover:bg-gift-50 transition-colors"
            >
              Try AI Search
            </Link>
          </div>
        </div>
      </section>

      {/* Quick-start cards */}
      <section className="mx-auto w-full max-w-6xl px-4 py-16">
        <div className="text-center mb-10">
          <h2 className="text-2xl sm:text-3xl font-bold text-warm-900 mb-3">
            Get started in seconds
          </h2>
          <p className="text-warm-600">
            Pick a quick-start profile or customize your own in the discovery browser.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {quickStartCards.map((card) => (
            <Link
              key={card.href}
              href={card.href}
              className={`group relative flex flex-col gap-1 rounded-2xl bg-gradient-to-br ${card.bg} border border-warm-200 p-6 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200`}
            >
              <span className="text-3xl mb-1" aria-hidden="true">
                {card.emoji}
              </span>
              <span className="font-semibold text-warm-900 text-lg">{card.label}</span>
              <span className="text-warm-600 text-sm">{card.occasion}</span>
              <span className="text-gift-600 text-sm font-medium">{card.budget}</span>
              <span className="absolute bottom-4 right-4 text-warm-400 group-hover:text-gift-500 transition-colors text-xl">
                →
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="bg-warm-100 py-16 px-4">
        <div className="mx-auto max-w-4xl text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-warm-900 mb-12">
            How Gift Finder works
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
            {[
              {
                step: '01',
                title: 'Describe the recipient',
                desc: 'Tell us their age, relationship, interests, and occasion.',
              },
              {
                step: '02',
                title: 'Browse curated results',
                desc: 'We surface gifts from hundreds of curated products matching your criteria.',
              },
              {
                step: '03',
                title: 'Save & share',
                desc: 'Build wishlists, share them, and check off gifts as you shop.',
              },
            ].map((item) => (
              <div key={item.step} className="flex flex-col items-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gift-500 text-white font-bold text-lg mb-4">
                  {item.step}
                </div>
                <h3 className="font-semibold text-warm-900 text-lg mb-2">{item.title}</h3>
                <p className="text-warm-600 text-sm">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
