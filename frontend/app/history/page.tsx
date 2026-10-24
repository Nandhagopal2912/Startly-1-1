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
    <div className="min-h-screen bg-slate-50/50 text-slate-900">
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-4 px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl premium-gradient text-white shadow-lg shadow-blue-500/20">
              <Zap size={20} fill="currentColor" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-slate-900">Startly <span className="text-indigo-600">Analyze</span></h1>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">Traffic Opportunity Tool</p>
            </div>
          </Link>
          <Link
            href="/"
            className="inline-flex items-center gap-2 h-11 px-4 rounded-2xl border border-slate-200 bg-white text-sm font-semibold text-slate-600 shadow-sm hover:border-indigo-200 hover:text-indigo-600 transition-colors"
          >
            <ArrowLeft size={18} />
            Dashboard
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] px-6 py-10">
        <div className="glass-card rounded-[2.5rem] overflow-hidden border border-slate-200/60 shadow-xl shadow-slate-200/40 bg-white">
          <div className="px-10 py-8 border-b border-slate-100 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <History size={20} />
              </div>
              <div>
                <h2 className="text-2xl font-black text-slate-900 tracking-tight">Saved Analyses</h2>
                <p className="text-sm text-slate-400 font-medium">Every analysis, newest first. Click one to reopen it. Reopening is free.</p>
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
            <div className="mx-10 mt-6 flex items-center gap-2 rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
              <AlertCircle size={16} /> {error}
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50/50 text-[11px] font-black text-slate-400 uppercase tracking-widest">
                  <th className="px-10 py-5">Analyzed</th>
                  <th className="px-6 py-5">Keyword</th>
                  <th className="px-6 py-5 text-right">Volume</th>
                  <th className="px-6 py-5 text-right">Clicks</th>
                  <th className="px-6 py-5 text-right">Click loss</th>
                  <th className="px-6 py-5 text-center">Click access</th>
                  <th className="px-10 py-5">Data</th>
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
                      <td className="px-10 py-5 text-sm font-medium text-slate-500 whitespace-nowrap">{formatWhen(item.created_at)}</td>
                      <td className="px-6 py-5">
                        <div className="font-extrabold text-slate-900">{item.keyword}</div>
                        <div className="text-[11px] font-medium text-slate-400">{item.location} · {item.language}</div>
                      </td>
                      <td className="px-6 py-5 text-right tabular-nums font-bold text-slate-500">
                        {known ? formatNumber(item.raw_volume) : "—"}
                        <div className="text-[10px] font-semibold text-slate-400">{volumeLabel(item.volume_source)}</div>
                      </td>
                      <td className="px-6 py-5 text-right tabular-nums font-black text-slate-900">
                        {known ? formatNumber(item.adjusted_volume) : "—"}
                        {known && low != null && high != null && low !== high && (
                          <div className="text-[10px] font-semibold text-slate-400">{formatNumber(low)}–{formatNumber(high)}</div>
                        )}
                      </td>
                      <td className="px-6 py-5 text-right tabular-nums font-bold text-slate-600">{item.penalty_percent}%</td>
                      <td className="px-6 py-5 text-center">
                        <span className={cn("inline-flex px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-wider", tier.className)}>
                          {tier.label}
                        </span>
                      </td>
                      <td className="px-10 py-5 text-xs font-semibold text-slate-400 capitalize">
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
