"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

export default function DashboardPage() {
  const { user, loading, isAuthenticated, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [loading, isAuthenticated, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 text-white">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
          <p className="text-lg font-medium">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="flex flex-col gap-6 rounded-3xl border border-slate-200 bg-white p-10 shadow-xl">
          <div className="flex flex-col gap-3">
            <p className="text-sm uppercase tracking-[0.3em] text-indigo-600">Welcome to Startly</p>
            <h1 className="text-4xl font-black tracking-tight">Dashboard</h1>
            <p className="max-w-2xl text-slate-500">You are signed in and can now access your analyses, tasks, and saved keyword history.</p>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6">
              <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Signed in as</p>
              <p className="mt-3 text-lg font-semibold text-slate-900">{user?.email ?? 'Unknown user'}</p>
              <p className="mt-2 text-sm text-slate-500">User ID: {user?.id ?? 'N/A'}</p>
            </div>
            <Link href="/activities" className="rounded-3xl border border-indigo-100 bg-indigo-600 px-6 py-6 text-white shadow-lg transition hover:bg-indigo-700">
              <p className="font-black text-sm uppercase tracking-[0.3em]">Your Tasks</p>
              <p className="mt-3 text-lg">View saved analyses and activity history</p>
            </Link>
            <button onClick={logout} className="rounded-3xl border border-slate-200 bg-white px-6 py-6 text-slate-900 shadow-lg transition hover:bg-slate-100">
              <p className="font-black text-sm uppercase tracking-[0.3em]">Sign Out</p>
              <p className="mt-3 text-lg">End session and return to login</p>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
