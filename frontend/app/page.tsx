"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, History, KeyRound, ListOrdered, Loader2, Search, XCircle, Zap } from "lucide-react";
import { cn } from "../lib/utils";
import { BulkAnalysis } from "../components/BulkAnalysis";
import { CreditsStatus } from "../components/CreditsStatus";
import { DetailsPanel } from "../components/DetailsPanel";
import { KeyDialog, type KeyInfo } from "../components/KeyDialog";
import { type ExportFormat, type ExportScope, KeywordList } from "../components/KeywordList";
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
  readProviderChoice,
  rowCountry,
  type ProviderName,
  writeProviderChoice,
  writeClearedAfterId,
} from "../lib/analysis";
import {
  KEY_HEADER,
  type LocalAnalysis,
  addLocal,
  dashboardLocal,
  deleteAllLocal,
  forgetKey,
  getLocal,
  hideAllLocal,
  hideLocal,
  keyTransportIsSecure,
  latestLocal,
  listLocal,
  previousCheck,
  previousLocal,
  readKey,
  saveKey,
  updateLocal,
} from "../lib/ownKey";

type Usage = { serp_provider: string; serp_configured: boolean; calls_today: number; daily_cap: number; demo_mode?: boolean };

const README_URL = "https://github.com/Nandhagopal2912/Startly-1-1#readme";

// File-name-safe version of a keyword: "what is a roth ira" -> "what-is-a-roth-ira".
const slug = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "keyword";

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
  const [creditsTick, setCreditsTick] = useState(0);
  // Which server provider this browser analyzes with; null = the server's SERP_PROVIDER.
  const [serpChoice, setSerpChoice] = useState<ProviderName | null>(null);
  const [demoKeywords, setDemoKeywords] = useState<string[]>([]);
  const demo = Boolean(usage?.demo_mode);
  // Visitor's own SerpApi key (public demo): kept in their browser, sent only with their searches.
  const [ownKey, setOwnKey] = useState<string | null>(null);
  const [keyInfo, setKeyInfo] = useState<KeyInfo | null>(null);
  const [keyDialog, setKeyDialog] = useState<{ reason?: string } | null>(null);
  const [localCount, setLocalCount] = useState(0);
  // Never send the key over an insecure connection, even if one is saved (lib/ownKey.ts keyTransportIsSecure).
  const keyHeaders = ownKey && keyTransportIsSecure() ? { [KEY_HEADER]: ownKey } : undefined;
  const restoredOnce = useRef(false);

  function countSearchOnOwnKey() {
    // Each search on the visitor's key uses one of their credits; keep the shown count roughly current.
    setKeyInfo((info) => (info && info.searches_left != null ? { ...info, searches_left: Math.max(info.searches_left - 1, 0) } : info));
  }

  function saveLocalRow(row: AnalysisRow, replace?: LocalAnalysis): LocalAnalysis {
    const entry = replace ? { ...row, local_id: replace.local_id } : addLocal(row);
    if (replace) updateLocal(entry);
    setLocalCount(listLocal().length);
    return entry;
  }

  const selectedRow = useMemo(
    () => rows.find((r) => r.keyword === selectedKeyword) ?? rows[0] ?? null,
    [rows, selectedKeyword]
  );

  async function refreshUsage() {
    setCreditsTick((n) => n + 1);
    try {
      const res = await fetch(`${API_BASE}/health/provider`);
      if (res.ok) setUsage(await res.json());
    } catch {
      setUsage(null);
    }
  }

  // Show how many searches the visitor's key has left (SerpApi's account check is free).
  useEffect(() => {
    if (!demo || !ownKey || !keyTransportIsSecure()) return;
    postJson<KeyInfo>("/key/check", {}, { [KEY_HEADER]: ownKey })
      .then(setKeyInfo)
      .catch(() => setKeyInfo(null));
  }, [demo, ownKey]);

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
    // Run once. React's dev mode runs effects twice, and the URL is cleaned up after the first run.
    if (restoredOnce.current) return;
    restoredOnce.current = true;
    refreshUsage();
    setOwnKey(readKey());
    setSerpChoice(readProviderChoice());
    setLocalCount(listLocal().length);
    async function restore() {
      const params = new URLSearchParams(window.location.search);
      const local = dashboardLocal();
      const openedLocal = params.get("local") ? getLocal(params.get("local")!) : undefined;
      if (local.length || openedLocal) {
        const first = openedLocal ?? local[0];
        setRows([first, ...local.filter((r) => r.local_id !== first.local_id && !sameKeyword(r, first))]);
        setSelectedKeyword(first.keyword);
        if (openedLocal) window.history.replaceState(null, "", window.location.pathname);
      }
      try {
        const openId = Number(params.get("open")) || null;
        const res = await fetch(`${API_BASE}/history/latest?limit=30&after_id=${readClearedAfterId()}`);
        const hidden = readHidden();
        const restored: AnalysisRow[] = res.ok ? (await res.json()).filter((r: AnalysisRow) => !isHidden(r, hidden)) : [];
        let opened: AnalysisRow | null = null;
        if (openId) {
          const one = await fetch(`${API_BASE}/history/${openId}`);
          if (one.ok) opened = await one.json();
          else setError("That saved analysis could not be found.");
        }
        const incoming = opened ? [opened, ...restored.filter((r) => !sameKeyword(r, opened!))] : restored;
        setRows((prev) => [...prev, ...incoming.filter((r) => !prev.some((p) => sameKeyword(p, r)))]);
        if (opened) {
          setSelectedKeyword(opened.keyword);
          window.history.replaceState(null, "", window.location.pathname);
        }
      } catch {
        setError("Can't reach the backend on port 8000. Start it with: uvicorn main:app --port 8000");
      } finally {
        setRestoring(false);
      }
    }
    restore();
  }, []);

  async function onAnalyze(e: FormEvent) {
    e.preventDefault();
    await analyzeKeyword(keyword);
  }

  async function analyzeKeyword(text: string) {
    if (!text.trim()) return;
    setError("");
    const typedVolume = volume.trim() === "" ? null : Number(volume.replace(/[,\s]/g, ""));
    if (demo) {
      const saved = latestLocal(text, country);
      if (saved && typedVolume === null) {
        // Already analyzed in this browser: reopen it for free.
        upsertRow(saved);
        setKeyword("");
        return;
      }
      if (ownKey && !demoKeywords.some((k) => k.toLowerCase() === text.trim().toLowerCase())) {
        await analyzeWithOwnKey(text.trim(), typedVolume ?? (saved?.volume_source === "user" ? saved.raw_volume : null), saved);
        return;
      }
    }
    setLoading(true);
    try {
      const fresh = await postJson<AnalysisRow>("/analyze", {
        keyword: text.trim(),
        location_name: country,
        language_name: "English",
        mock_mode: mockMode && !demo,
        provider: demo ? undefined : serpChoice ?? undefined,
        search_volume: volume.trim() === "" ? null : Number(volume.replace(/[,\s]/g, "")),
      });
      upsertRow(fresh);
      setKeyword("");
      setVolume("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Analysis failed";
      if (demo && message.includes("isn't in the demo")) {
        setKeyDialog({ reason: `"${text.trim()}" isn't one of the samples. Add your own free SerpApi key to analyze it.` });
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
      refreshUsage();
    }
  }

  // Search on the visitor's own key; the result (and its results page) is saved in their browser.
  async function analyzeWithOwnKey(text: string, searchVolume: number | null, previous?: AnalysisRow) {
    if (!ownKey || !keyHeaders) {
      setKeyDialog({});
      return;
    }
    setLoading(true);
    try {
      const fresh = await postJson<AnalysisRow>(
        "/analyze",
        { keyword: text, location_name: country, language_name: "English", search_volume: searchVolume, previous: previousCheck(previous) },
        keyHeaders
      );
      countSearchOnOwnKey();
      upsertRow(saveLocalRow(fresh));
      setKeyword("");
      setVolume("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  // Re-score the saved results page with a new volume. cache_only guarantees no API call.
  async function saveVolume(row: AnalysisRow, newVolume: number) {
    setError("");
    setSavingVolume(true);
    try {
      if (row.own_key && row.snapshot && row.snapshot_fetched_at) {
        const local = row.local_id ? getLocal(row.local_id) : undefined;
        const rescored = await postJson<AnalysisRow>("/rescore", {
          keyword: row.keyword,
          location_name: rowCountry(row),
          language_name: row.language_name ?? "English",
          search_volume: newVolume,
          snapshot: row.snapshot,
          snapshot_fetched_at: row.snapshot_fetched_at,
          previous: local ? previousCheck(previousLocal(local)) : undefined,
        });
        upsertRow(local ? saveLocalRow(rescored, local) : rescored);
        return;
      }
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
    if (demo && ownKey) {
      const left = keyInfo?.searches_left;
      return `Re-checking uses 1 search on your SerpApi key${left != null ? ` (${left} left)` : ""}.`;
    }
    if (demo) return "Add your own SerpApi key to re-check keywords.";
    if (row.mock_mode) return "Mock mode: re-checking is free.";
    if (!usage) return "Re-checking uses 1 API call.";
    const left = Math.max(usage.daily_cap - usage.calls_today, 0);
    return `Re-checking uses 1 ${usage.serp_provider} search (${left} of ${usage.daily_cap} left today).`;
  }

  // Fetch the results page again (skipping the cache) and compare it with the previous check.
  async function recheck(row: AnalysisRow) {
    if (!row.mock_mode && !window.confirm(`Re-check "${row.keyword}" now?\n\n${recheckCostNote(row)}`)) return;
    if (demo && ownKey) {
      if (!keyHeaders) {
        setKeyDialog({});
        return;
      }
      setRechecking(true);
      setError("");
      try {
        const fresh = await postJson<AnalysisRow>(
          "/analyze",
          {
            keyword: row.keyword,
            location_name: rowCountry(row),
            language_name: row.language_name ?? "English",
            search_volume: row.volume_source && row.volume_source !== "unknown" ? row.raw_volume : null,
            previous: previousCheck(row),
          },
          keyHeaders
        );
        countSearchOnOwnKey();
        upsertRow(saveLocalRow(fresh));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Re-check failed");
      } finally {
        setRechecking(false);
      }
      return;
    }
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
          provider: serpChoice ?? undefined,
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
    if (row?.local_id) hideLocal(row.keyword);
    if (row?.analysis_id) hideKeyword(row.keyword, row.analysis_id);
    setRows((prev) => prev.filter((r) => r.keyword !== kw));
    if (selectedKeyword === kw) setSelectedKeyword(null);
  }

  function clearDashboard() {
    if (!window.confirm("Remove all keywords from the dashboard? They stay in History.")) return;
    writeClearedAfterId(Math.max(readClearedAfterId(), ...rows.map((r) => r.analysis_id ?? 0)));
    hideAllLocal();
    setRows([]);
    setSelectedKeyword(null);
  }

  // Bulk results join the dashboard list, so the keyword list and exports include them.
  function addBulkResults(results: AnalysisRow[]) {
    if (!results.length) return;
    // New searches on the visitor's key are saved in their browser; rows already saved there come back as-is.
    const newRows = results.map((r) => (r.own_key && !r.local_id ? saveLocalRow(r) : r));
    const searches = results.filter((r) => r.own_key && !r.local_id).length;
    if (searches) setKeyInfo((info) => (info && info.searches_left != null ? { ...info, searches_left: Math.max(info.searches_left - searches, 0) } : info));
    setRows((prev) => [...newRows, ...prev.filter((r) => !newRows.some((n) => sameKeyword(n, r)))]);
    setSelectedKeyword(newRows[0].keyword);
  }

  async function onExport(format: ExportFormat, scope: ExportScope) {
    const chosen = scope === "selected" && selectedRow ? [selectedRow] : rows;
    if (!chosen.length) return;
    setError("");
    try {
      const res = await fetch(`${API_BASE}/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          format,
          // Everything the exports show; the browser-only fields (key, saved results page) stay here.
          rows: chosen.map((r) => ({
            keyword: r.keyword,
            raw_volume: r.raw_volume,
            volume_source: r.volume_source ?? "",
            adjusted_volume: r.adjusted_volume,
            capturable_clicks: r.capturable_clicks ?? null,
            capturable_clicks_low: r.capturable_clicks_low ?? null,
            capturable_clicks_high: r.capturable_clicks_high ?? null,
            saturation_score: r.saturation_score,
            organic_results: r.organic_results,
            total_results: r.total_results,
            penalty_applied: r.penalty_applied,
            source: r.source,
            mock_mode: r.mock_mode,
            location_name: rowCountry(r),
            provider: r.provider ?? null,
            analyzed_at: r.analyzed_at ?? null,
            changes: r.changes ?? null,
            rescored: Boolean(r.rescored),
            own_key: Boolean(r.own_key),
            report: r.report ?? null,
          })),
        }),
      });
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const name = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") ?? "")?.[1] ?? `startly-export.${format === "pdf" ? "pdf" : "csv"}`;
      const url = window.URL.createObjectURL(await res.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = scope === "selected" ? name.replace("startly-report", `startly-${slug(chosen[0].keyword)}`) : name;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    }
  }


  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {bulkOpen && (
        <BulkAnalysis
          mockMode={mockMode}
          location={country}
          ownKey={demo ? ownKey : null}
          provider={demo ? null : serpChoice}
          onClose={() => setBulkOpen(false)}
          onResults={addBulkResults}
          onOpenKeyword={(kw) => {
            setSelectedKeyword(kw);
            setBulkOpen(false);
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        />
      )}

      {keyDialog && (
        <KeyDialog
          demo={demo}
          reason={keyDialog.reason}
          localCount={localCount}
          onClose={() => setKeyDialog(null)}
          onSave={(key, remember, info) => {
            saveKey(key, remember);
            setOwnKey(key);
            setKeyInfo(info);
            setKeyDialog(null);
          }}
          onForget={() => {
            forgetKey();
            setOwnKey(null);
            setKeyInfo(null);
            setKeyDialog(null);
          }}
          onDeleteData={() => {
            deleteAllLocal();
            setLocalCount(0);
            setRows((prev) => prev.filter((r) => !r.local_id));
            setKeyDialog(null);
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
                placeholder={demo && !ownKey ? "Pick a sample keyword, or use your own key for any keyword" : "Keyword to analyze, e.g. best crm software"}
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
            {/* Shown in both modes so a key saved in this browser can always be checked or forgotten.
                Normal mode searches with the server's .env key; a saved key is only used on the public demo. */}
            <button
              type="button"
              onClick={() => setKeyDialog({})}
              className={cn(
                "inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-sm font-medium",
                ownKey
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : demo
                    ? "border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100"
                    : "border-slate-200 bg-white text-slate-700 hover:border-indigo-200 hover:text-indigo-600"
              )}
              title={
                demo
                  ? ownKey ? "Your SerpApi key is set" : "Analyze any keyword with your own free SerpApi key"
                  : ownKey ? "A SerpApi key is saved in this browser (used only on the public demo)" : "Save or manage your own SerpApi key"
              }
            >
              <KeyRound size={16} /> {ownKey ? "Your key" : demo ? "Use your key" : "Key"}
            </button>
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
              ownKey ? (
                <span className="font-semibold text-emerald-700">
                  Using your SerpApi key{keyInfo?.searches_left != null ? `: ${keyInfo.searches_left} searches left` : ""}. Your analyses are saved
                  in this browser only.
                </span>
              ) : (
                <span className="font-semibold text-indigo-700">
                  Public demo: explore the samples for free, or{" "}
                  <button type="button" onClick={() => setKeyDialog({})} className="underline">
                    add your own free SerpApi key
                  </button>{" "}
                  to analyze any keyword.{" "}
                  <a href={README_URL} target="_blank" rel="noreferrer" className="font-normal underline">
                    Or run Startly yourself
                  </a>
                </span>
              )
            ) : (
            <label className="inline-flex cursor-pointer items-center gap-2">
              <input type="checkbox" checked={mockMode} onChange={(e) => setMockMode(e.target.checked)} className="h-3.5 w-3.5 accent-amber-500" />
              <span className={mockMode ? "font-semibold text-amber-700" : ""}>
                Mock data {mockMode ? "on: free, fake results" : "(free, for testing)"}
              </span>
            </label>
            )}
            {!demo && (
              <CreditsStatus
                refreshSignal={creditsTick}
                selected={serpChoice}
                onSelect={(choice) => {
                  setSerpChoice(choice);
                  writeProviderChoice(choice);
                }}
              />
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
              <VerdictHero row={selectedRow} demo={demo && !selectedRow.own_key} savingVolume={savingVolume} onSaveVolume={(v) => saveVolume(selectedRow, v)} />
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
                onRecheck={demo && !ownKey ? undefined : () => recheck(selectedRow)}
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
