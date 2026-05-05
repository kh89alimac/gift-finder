import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { Toaster } from 'sonner';
import { NuqsAdapter } from 'nuqs/adapters/next/app';
import { QueryProvider } from '../providers/QueryProvider';
import { AuthProvider } from '../providers/AuthProvider';
import Header from '../components/layout/Header';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'Gift Finder — Find the Perfect Gift',
    template: '%s | Gift Finder',
  },
  description:
    'Discover personalized gift ideas for every occasion, budget, and recipient. Powered by AI.',
  keywords: ['gifts', 'gift ideas', 'birthday', 'anniversary', 'present'],
  openGraph: {
    type: 'website',
    title: 'Gift Finder',
    description: 'Find the perfect gift for anyone.',
    siteName: 'Gift Finder',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-warm-50 text-warm-950 antialiased">
        <NuqsAdapter>
          <QueryProvider>
            <AuthProvider>
              <Header />
              <main>{children}</main>
              <Toaster
                position="bottom-right"
                toastOptions={{
                  style: {
                    background: '#fdf6ee',
                    border: '1px solid #f5d2a8',
                    color: '#3d1407',
                  },
                }}
              />
            </AuthProvider>
          </QueryProvider>
        </NuqsAdapter>
      </body>
    </html>
  );
}
