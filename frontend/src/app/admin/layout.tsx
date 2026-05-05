'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import useAuthStore from '../../lib/store/authStore';
import AdminSidebar from '../../components/admin/AdminSidebar';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { isAdmin, user } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (!user) {
      router.replace('/auth/login');
      return;
    }
    if (!isAdmin()) {
      router.replace('/');
    }
  }, [user, isAdmin, router]);

  if (!user || !isAdmin()) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 rounded-full border-4 border-gift-300 border-t-gift-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-64px)]">
      <AdminSidebar />
      <main className="flex-1 overflow-auto bg-warm-50 p-6">
        {children}
      </main>
    </div>
  );
}
