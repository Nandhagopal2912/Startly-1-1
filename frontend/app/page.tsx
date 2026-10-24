"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, History, ListOrdered, Loader2, Search, XCircle, Zap } from "lucide-react";
import { cn } from "../lib/utils";
import { BulkAnalysis } from "../components/BulkAnalysis";
import { DetailsPanel } from "../components/DetailsPanel";
import { KeywordList } from "../components/KeywordList";
import { PageOne } from "../components/PageOne";
import { Recommendations } from "../components/Recommendations";
import { VerdictHero } from "../components/VerdictHero";
import { WhatChanged } from "../components/WhatChanged";
import {
  API_BASE,
  COUNTRIES,
  DEFAULT_COUNTRY,
  type AnalysisRow,
  type SortKey,
  hideKeyword,
  isHidden,
  postJson,
  readClearedAfterId,
  readHidden,
  rowCountry,
  writeClearedAfterId,
} from "../lib/analysis";

type Usage = { serp_provider: string; serp_configured: boolean; calls_today: number; daily_cap: number; demo_mode?: boolean };

const README_URL = "https://github.com/Nandhagopal2912/Startly-1-1#readme";

const sameKeyword = (a: AnalysisRow, b: AnalysisRow) => a.keyword.toLowerCase() === b.keyword.toLowerCase();

export default function HomePage() {
  const [keyword, setKeyword] = useState("");
  const [volume, setVolume] = useState("");
  const [country, setCountry] = useState(DEFAULT_COUNTRY);
  const [mockMode, setMockMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rows, setRows] = useState<AnalysisRow[]>([]);
  const [restoring, setRestoring] = useState(true);
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("clicks");
  const [bulkOpen, setBulkOpen] = useState(false);
  const [rechecking, setRechecking] = useState(false);
  const [savingVolume, setSavingVolume] = useState(false);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [demoKeywords, setDemoKeywords] = useState<string[]>([]);
  const demo = Boolean(usage?.demo_mode);

  const selectedRow = useMemo(
    () => rows.find((r) => r.keyword === selectedKeyword) ?? rows[0] ?? null,
    [rows, selectedKeyword]
  );

  async function refreshUsage() {
    try {
      const res = await fetch(`${API_BASE}/health/provider`);
      if (res.ok) setUsage(await res.json());
    } catch {
      setUsage(null);
    }
  }

  useEffect(() => {
    if (!demo) return;
    fetch(`${API_BASE}/demo/keywords`)
      .then((r) => (r.ok ? r.json() : []))
      .then((list: { keyword: string }[]) => setDemoKeywords(list.map((k) => k.keyword)))
      .catch(() => setDemoKeywords([]));
  }, [demo]);

  // Put a fresh analysis on the dashboard, replacing any older one of the same keyword.
  function upsertRow(fresh: AnalysisRow) {
    setRows((prev) => {
      const i = prev.findIndex((r) => sameKeyword(r, fresh));
      if (i === -1) return [fresh, ...prev];
      const next = [...prev];
      next[i] = fresh;
      return next;
    });
    setSelectedKeyword(fresh.keyword);
  }

  // Restore recent analyses (no API calls) and open one if the URL asks: /?open=<analysis id>.
  useEffect(() => {
    let cancelled = false;
    refreshUsage();
    async function restore() {
      try {
        const openId = Number(new URLSearchParams(window.location.search).get("open")) || null;
        const res = await fetch(`${API_BASE}/history/latest?limit=30&after_id=${readClearedAfterId()}`);
        const hidden = readHidden();
        const restored: AnalysisRow[] = res.ok ? (await res.json()).filter((r: AnalysisRow) => !isHidden(r, hidden)) : [];
        let opened: AnalysisRow | null = null;
        if (openId) {
          const one = await fetch(`${API_BASE}/history/${openId}`);
          if (one.ok) opened = await one.json();
          else if (!cancelled) setError("That saved analysis could not be found.");
        }
        if (cancelled) return;
        const incoming = opened ? [opened, ...restored.filter((r) => !sameKeyword(r, opened!))] : restored;
        setRows((prev) => [...prev, ...incoming.filter((r) => !prev.some((p) => sameKeyword(p, r)))]);
        if (opened) {
          setSelectedKeyword(opened.keyword);
          window.history.replaceState(null, "", window.location.pathname);
        }
      } catch {
        if (!cancelled) setError("Can't reach the backend on port 8000. Start it with: uvicorn main:app --port 8000");
      } finally {
        if (!cancelled) setRestoring(false);
      }
    }
    restore();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onAnalyze(e: FormEvent) {
    e.preventDefault();
    await analyzeKeyword(keyword);
  }

  async function analyzeKeyword(text: string) {
    if (!text.trim()) return;
    setError("");
    setLoading(true);
    try {
      const fresh = await postJson<AnalysisRow>("/analyze", {
        keyword: text.trim(),
        location_name: country,
        language_name: "English",
        mock_mode: mockMode && !demo,
        search_volume: volume.trim() === "" ? null : Number(volume.replace(/[,\s]/g, "")),
      });
      upsertRow(fresh);
      setKeyword("");
      setVolume("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
      refreshUsage();
    }
  }

  // Re-score the saved results page with a new volume. cache_only guarantees no API call.
  async function saveVolume(row: AnalysisRow, newVolume: number) {
    setError("");
    setSavingVolume(true);
    try {
      upsertRow(
        await postJson<AnalysisRow>("/analyze", {
          keyword: row.keyword,
          location_name: rowCountry(row),
          language_name: row.language_name ?? "English",
          mock_mode: row.mock_mode,
          search_volume: newVolume,
          cache_only: true,
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the volume");
    } finally {
      setSavingVolume(false);
    }
  }

  function recheckCostNote(row: AnalysisRow) {
    if (demo) return "Re-checking is turned off in the public demo.";
    if (row.mock_mode) return "Mock mode: re-checking is free.";
    if (!usage) return "Re-checking uses 1 API call.";
    const left = Math.max(usage.daily_cap - usage.calls_today, 0);
    return `Re-checking uses 1 ${usage.serp_provider} search (${left} of ${usage.daily_cap} left today).`;
  }

  // Fetch the results page again (skipping the cache) and compare it with the previous check.
  async function recheck(row: AnalysisRow) {
    if (!row.mock_mode && !window.confirm(`Re-check "${row.keyword}" now?\n\n${recheckCostNote(row)}`)) return;
    setError("");
    setRechecking(true);
    try {
      upsertRow(
        await postJson<AnalysisRow>("/analyze", {
          keyword: row.keyword,
          location_name: rowCountry(row),
          language_name: row.language_name ?? "English",
          mock_mode: row.mock_mode,
          refresh: true,
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-check failed");
    } finally {
      setRechecking(false);
      refreshUsage();
    }
  }

  function removeRow(kw: string) {
    const row = rows.find((r) => r.keyword === kw);
    if (row?.analysis_id) hideKeyword(row.keyword, row.analysis_id);
    setRows((prev) => prev.filter((r) => r.keyword !== kw));
    if (selectedKeyword === kw) setSelectedKeyword(null);
  }

  function clearDashboard() {
    if (!window.confirm("Remove all keywords from the dashboard? They stay in History.")) return;
    writeClearedAfterId(Math.max(readClearedAfterId(), ...rows.map((r) => r.analysis_id ?? 0)));
    setRows([]);
    setSelectedKeyword(null);
  }

  // Bulk results join the dashboard list, so the keyword list and exports include them.
  function addBulkResults(newRows: AnalysisRow[]) {
    if (!newRows.length) return;
    setRows((prev) => [...newRows, ...prev.filter((r) => !newRows.some((n) => sameKeyword(n, r)))]);
    setSelectedKeyword(newRows[0].keyword);
  }

  async function onExport(format: "csv" | "pdf") {
    if (!rows.length) return;
    setError("");
    try {
      const res = await fetch(`${API_BASE}/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          format,
          rows: rows.map((r) => ({
            keyword: r.keyword,
            raw_volume: r.raw_volume,
            volume_source: r.volume_source ?? "",
            adjusted_volume: r.adjusted_volume,
            saturation_score: r.saturation_score,
            organic_results: r.organic_results,
            total_results: r.total_results,
            penalty_applied: r.penalty_applied,
            source: r.source,
            mock_mode: r.mock_mode,
            report: r.report ?? null,
          })),
        }),
      });
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const url = window.URL.createObjectURL(await res.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = `startly-keywords.${format}`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    }
  }

  const callsLeft = usage ? Math.max(usage.daily_cap - usage.calls_today, 0) : null;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {bulkOpen && (
        <BulkAnalysis
          apiBase={API_BASE}
          mockMode={mockMode}
          location={country}
          onClose={() => setBulkOpen(false)}
          onResults={addBulkResults}
          onOpenKeyword={(kw) => {
            setSelectedKeyword(kw);
            setBulkOpen(false);
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        />
      )}

      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl premium-gradient text-white">
              <Zap size={18} fill="currentColor" />
            </span>
            <span className="text-base font-bold tracking-tight">
              Startly <span className="text-indigo-600">Analyze</span>
            </span>
          </Link>

          <form onSubmit={onAnalyze} className="order-last flex w-full flex-wrap items-center gap-2 xl:order-none xl:w-auto xl:flex-1">
            <div className="relative min-w-[200px] flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder={demo ? "Pick a sample keyword" : "Keyword to analyze, e.g. best crm software"}
                list={demo ? "demo-keywords" : undefined}
                aria-label="Keyword to analyze"
                className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              />
            </div>
            {demo && (
              <datalist id="demo-keywords">
                {demoKeywords.map((k) => (
                  <option key={k} value={k} />
                ))}
              </datalist>
            )}
            <input
              inputMode="numeric"
              value={volume}
              onChange={(e) => setVolume(e.target.value)}
              placeholder="Volume (optional)"
              aria-label="Monthly search volume (optional)"
              title="Monthly searches, e.g. from Google Keyword Planner. You can also add it after analyzing."
              className="h-10 w-36 rounded-xl border border-slate-200 bg-white px-3 text-sm tabular-nums focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
            <select
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              aria-label="Country"
              className="h-10 rounded-xl border border-slate-200 bg-white px-2 text-sm text-slate-700 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            >
              {COUNTRIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
            <button
              type="submit"
              disabled={loading || !keyword.trim()}
              className="inline-flex h-10 items-center gap-2 rounded-xl premium-gradient px-5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {loading && <Loader2 size={16} className="animate-spin" />}
              {loading ? "Analyzing…" : "Analyze"}
            </button>
          </form>

          <nav className="ml-auto flex items-center gap-2 xl:ml-0">
            <button
              type="button"
              onClick={() => setBulkOpen(true)}
              className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600"
              title="Analyze and rank a list of keywords"
            >
              <ListOrdered size={16} /> Bulk
            </button>
            <Link
              href="/history"
              className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600"
            >
              <History size={16} /> History
            </Link>
          </nav>
        </div>

        <div className="border-t border-slate-100 bg-slate-50/80">
          <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-5 gap-y-1 px-4 py-1.5 text-xs text-slate-500 sm:px-6">
            {demo ? (
              <span className="font-semibold text-indigo-700">
                Public demo: sample data, read-only.{" "}
                <a href={README_URL} target="_blank" rel="noreferrer" className="underline">
                  Run Startly yourself
                </a>{" "}
                to analyze any keyword.
              </span>
            ) : (
            <label className="inline-flex cursor-pointer items-center gap-2">
              <input type="checkbox" checked={mockMode} onChange={(e) => setMockMode(e.target.checked)} className="h-3.5 w-3.5 accent-amber-500" />
              <span className={mockMode ? "font-semibold text-amber-700" : ""}>
                Mock data {mockMode ? "on: free, fake results" : "(free, for testing)"}
              </span>
            </label>
            )}
            {demo ? null : usage ? (
              <span title="Paid searches made today against MAX_API_CALLS_PER_DAY">
                <span className={cn("mr-1.5 inline-block h-2 w-2 rounded-full", usage.serp_configured ? "bg-emerald-500" : "bg-rose-500")} />
                {usage.serp_configured ? `${usage.serp_provider}: ${callsLeft} of ${usage.daily_cap} searches left today` : `${usage.serp_provider} key missing in backend/.env`}
              </span>
            ) : (
              <span><span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-rose-500" />Backend offline</span>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6">
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="mb-6 flex items-start gap-3 rounded-2xl border border-rose-100 bg-rose-50 p-4 text-rose-800"
              role="alert"
            >
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <p className="text-sm">{error}</p>
              <button onClick={() => setError("")} className="ml-auto text-rose-400 hover:text-rose-600" aria-label="Dismiss">
                <XCircle size={18} />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {!selectedRow ? (
          restoring ? (
            <div className="flex justify-center py-32 text-slate-400">
              <Loader2 size={28} className="animate-spin" />
            </div>
          ) : (
            <EmptyState onBulk={() => setBulkOpen(true)} samples={demo ? demoKeywords : []} onSample={analyzeKeyword} />
          )
        ) : (
          <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
            <aside className="lg:sticky lg:top-32 lg:self-start">
              <KeywordList
                rows={rows}
                selectedKeyword={selectedRow.keyword}
                sortKey={sortKey}
                onSort={setSortKey}
                onSelect={setSelectedKeyword}
                onRemove={removeRow}
                onClear={clearDashboard}
                onExport={onExport}
              />
            </aside>

            <div className="min-w-0 space-y-6">
              <VerdictHero row={selectedRow} demo={demo} savingVolume={savingVolume} onSaveVolume={(v) => saveVolume(selectedRow, v)} />
              <div className="grid gap-6 xl:grid-cols-5">
                <div className="xl:col-span-2">
                  <Recommendations items={selectedRow.report?.recommendations} />
                </div>
                <div className="xl:col-span-3">
                  <PageOne row={selectedRow} />
                </div>
              </div>
              <WhatChanged
                changes={selectedRow.changes}
                rechecking={rechecking}
                costNote={recheckCostNote(selectedRow)}
                onRecheck={demo ? undefined : () => recheck(selectedRow)}
              />
              <DetailsPanel row={selectedRow} />
            </div>
          </div>
        )}
      </main>

      <footer className="mx-auto max-w-[1400px] px-4 pb-10 pt-6 text-xs text-slate-400 sm:px-6">
        Estimates use published click-through-rate studies; see the{" "}
        <a href="https://github.com/Nandhagopal2912/Startly-1-1/blob/main/METHODOLOGY.md" target="_blank" rel="noreferrer" className="underline hover:text-indigo-600">
          methodology
        </a>{" "}
        for sources and limits.
      </footer>
    </div>
  );
}

function EmptyState({ onBulk, samples, onSample }: { onBulk: () => void; samples: string[]; onSample: (kw: string) => void }) {
  const steps = [
    ["Enter a keyword", "Startly fetches Google's first page for it (cached keywords are free)."],
    ["Add its monthly volume", "From Google Keyword Planner, now or after analyzing."],
    ["Get a verdict", "Capturable clicks, what each ranking is worth, who ranks, and what to do."],
  ];
  return (
    <div className="mx-auto max-w-2xl py-20 text-center">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">How many clicks can this keyword really bring?</h1>
      <p className="mt-2 text-sm text-slate-500">
        Search volume overstates traffic. Startly subtracts what Google&apos;s AI Overviews, ads and maps take, and shows what&apos;s left for organic results.
      </p>
      <ol className="mt-10 grid gap-4 text-left sm:grid-cols-3">
        {steps.map(([title, detail], i) => (
          <li key={title} className="rounded-2xl border border-slate-200 bg-white p-4">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-50 text-sm font-semibold text-indigo-600">{i + 1}</span>
            <p className="mt-3 text-sm font-semibold text-slate-900">{title}</p>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">{detail}</p>
          </li>
        ))}
      </ol>
      {samples.length > 0 && (
        <div className="mt-8">
          <p className="text-sm font-semibold text-slate-700">Try a sample keyword</p>
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            {samples.slice(0, 12).map((kw) => (
              <button
                key={kw}
                type="button"
                onClick={() => onSample(kw)}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 hover:border-indigo-300 hover:text-indigo-700"
              >
                {kw}
              </button>
            ))}
          </div>
        </div>
      )}
      <p className="mt-8 text-sm text-slate-500">
        Have a list?{" "}
        <button type="button" onClick={onBulk} className="font-semibold text-indigo-600 hover:underline">
          Rank up to 50 keywords at once
        </button>
      </p>
    </div>
  );
}
