"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

export default function HomePage() {
  const { loading, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) {
      router.replace(isAuthenticated ? "/dashboard" : "/login");
    }
  }, [loading, isAuthenticated, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 text-white">
      <div className="text-center px-6 py-8 rounded-3xl bg-slate-950/80 shadow-2xl border border-white/10">
        <p className="text-lg font-medium">Checking authentication state...</p>
        <p className="mt-3 text-sm text-slate-400">If you are not signed in, you will be redirected to the login page.</p>
      </div>
    </div>
  );
}
