"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, ArrowLeft, History, Loader2, Search, Zap } from "lucide-react";
import { cn, formatNumber } from "../../lib/utils";
import { API_BASE, tierForLoss, volumeLabel } from "../../lib/analysis";

const PAGE_SIZE = 50;

type HistoryItem = {
  id: number;
  keyword: string;
  location: string;
  language: string;
  provider: string;
  raw_volume: number;
  volume_source: string;
  adjusted_volume: number;
  capturable_clicks_low: number | null;
  capturable_clicks_high: number | null;
  penalty_percent: number;
  organic_results: number;
  total_results: number;
  created_at: string;
  exact: boolean;
};

function formatWhen(iso: string) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function HistoryPage() {
  const router = useRouter();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");
  const requestSeq = useRef(0);

  const load = useCallback(async (q: string, offset: number) => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
      if (q.trim()) params.set("q", q.trim());
      const res = await fetch(`${API_BASE}/history?${params}`);
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      const page: HistoryItem[] = await res.json();
      if (seq !== requestSeq.current) return; // a newer search replaced this one
      setItems((prev) => (offset ? [...prev, ...page] : page));
      setHasMore(page.length === PAGE_SIZE);
    } catch (err) {
      if (seq === requestSeq.current) {
        setError(err instanceof Error && err.message.startsWith("Request") ? err.message : "Can't reach the backend. Is it running on port 8000?");
      }
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, []);

  // Search as you type, after a short pause.
  useEffect(() => {
    const t = window.setTimeout(() => load(query, 0), query ? 250 : 0);
    return () => window.clearTimeout(t);
  }, [query, load]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl premium-gradient text-white">
              <Zap size={18} fill="currentColor" />
            </span>
            <span className="text-base font-bold tracking-tight">
              Startly <span className="text-indigo-600">Analyze</span>
            </span>
          </Link>
          <Link
            href="/"
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600"
          >
            <ArrowLeft size={18} />
            Dashboard
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6">
        <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 px-6 py-5">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <History size={20} />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight text-slate-900">Saved analyses</h1>
                <p className="text-sm text-slate-500">Every analysis, newest first. Click one to reopen it; reopening is free.</p>
              </div>
            </div>
            <div className="relative w-full max-w-xs">
              <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search keywords"
                aria-label="Search saved analyses by keyword"
                className="w-full h-11 pl-10 pr-4 rounded-2xl border border-slate-200 bg-slate-100/50 text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
          </div>

          {error && (
            <div className="mx-6 mt-6 flex items-center gap-2 rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
              <AlertCircle size={16} /> {error}
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50 text-left text-xs font-medium text-slate-500">
                  <th className="px-6 py-3">Analyzed</th>
                  <th className="px-6 py-3">Keyword</th>
                  <th className="px-6 py-3 text-right font-medium">Volume</th>
                  <th className="px-6 py-3 text-right font-medium">Clicks</th>
                  <th className="px-6 py-3 text-right font-medium">Click loss</th>
                  <th className="px-6 py-3 text-center">Click access</th>
                  <th className="px-6 py-3">Data</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((item) => {
                  const known = item.volume_source !== "unknown";
                  const tier = tierForLoss(item.penalty_percent);
                  const { capturable_clicks_low: low, capturable_clicks_high: high } = item;
                  return (
                    <tr
                      key={item.id}
                      onClick={() => router.push(`/?open=${item.id}`)}
                      className="group cursor-pointer transition-all hover:bg-indigo-50/30"
                      title="Reopen this analysis on the dashboard"
                    >
                      <td className="px-6 py-3 text-sm font-medium text-slate-500 whitespace-nowrap">{formatWhen(item.created_at)}</td>
                      <td className="px-6 py-3">
                        <div className="font-semibold text-slate-900">{item.keyword}</div>
                        <div className="text-[11px] font-medium text-slate-400">{item.location} · {item.language}</div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-3 text-right tabular-nums font-bold text-slate-500">
                        {known ? formatNumber(item.raw_volume) : "—"}
                        <div className="text-[10px] font-semibold text-slate-400">{volumeLabel(item.volume_source)}</div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-3 text-right tabular-nums font-semibold text-slate-900">
                        {known ? formatNumber(item.adjusted_volume) : "—"}
                        {known && low != null && high != null && low !== high && (
                          <div className="text-[10px] font-semibold text-slate-400">{formatNumber(low)}–{formatNumber(high)}</div>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-6 py-3 text-right tabular-nums font-bold text-slate-600">{item.penalty_percent}%</td>
                      <td className="px-6 py-3 text-center">
                        <span className={cn("inline-flex px-3 py-1 rounded-full text-xs font-medium", tier.className)}>
                          {tier.label}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-xs font-semibold text-slate-400 capitalize">
                        {item.provider} · {item.organic_results}/{item.total_results} organic
                        {!item.exact && (
                          <div className="mt-1 normal-case font-medium text-amber-600" title="Saved before full results were stored">
                            Older analysis: reopens with today&apos;s click model
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {loading && (
            <div className="py-10 flex justify-center text-slate-400">
              <Loader2 size={24} className="animate-spin" />
            </div>
          )}
          {!loading && !error && items.length === 0 && (
            <p className="py-16 text-center text-sm font-bold text-slate-400">
              {query ? `No saved analyses match "${query}".` : "No analyses yet. Run one from the dashboard."}
            </p>
          )}
          {!loading && hasMore && (
            <div className="py-6 flex justify-center border-t border-slate-100">
              <button
                onClick={() => load(query, items.length)}
                className="px-6 py-3 rounded-2xl border border-slate-200 text-sm font-bold text-slate-600 hover:bg-slate-50"
              >
                Load more
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
