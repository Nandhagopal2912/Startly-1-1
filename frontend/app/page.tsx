"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
  PointElement,
  LineElement,
  ArcElement,
} from "chart.js";
import { Bar, Doughnut } from "react-chartjs-2";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Search, 
  Zap, 
  BarChart3, 
  PieChart, 
  AlertCircle, 
  TrendingUp, 
  TrendingDown, 
  Info, 
  Layers, 
  History,
  CheckCircle2,
  XCircle,
  MoreHorizontal,
  ArrowRight,
  Download,
  ListOrdered,
  FileText
} from "lucide-react";
import { cn, formatNumber } from "../lib/utils";
import { InsightsPanel, type FullReport } from "../components/AnalyzeReport";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { ClicksByPosition } from "../components/ClicksByPosition";
import { BulkAnalysis } from "../components/BulkAnalysis";
import { WhatChanged } from "../components/WhatChanged";
import {
  API_BASE,
  type AnalysisRow,
  clickTier,
  clicksDescription,
  clicksValue,
  hasVolume,
  readClearedAfterId,
  volumeLabel,
  writeClearedAfterId,
} from "../lib/analysis";

ChartJS.register(
  CategoryScale, 
  LinearScale, 
  BarElement, 
  PointElement, 
  LineElement, 
  ArcElement, 
  Tooltip, 
  Legend
);

export default function HomePage() {
  const [keyword, setKeyword] = useState("");
  const [mockMode, setMockMode] = useState(false);
  const [volume, setVolume] = useState("");
  const [loading, setLoading] = useState(false);
  const [pageReady, setPageReady] = useState(false);
  const [error, setError] = useState("");
  const [rows, setRows] = useState<AnalysisRow[]>([]);
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [rechecking, setRechecking] = useState(false);
  const [usage, setUsage] = useState<{ serp_provider: string; calls_today: number; daily_cap: number } | null>(null);

  async function refreshUsage() {
    try {
      const res = await fetch(`${API_BASE}/health/provider`);
      if (res.ok) setUsage(await res.json());
    } catch {
      /* usage note is optional */
    }
  }

  useEffect(() => {
    refreshUsage();
  }, []);

  function recheckCostNote(row: AnalysisRow) {
    if (row.mock_mode) return "Mock mode: re-checking is free.";
    if (!usage) return "Re-checking uses 1 API call.";
    const left = Math.max(usage.daily_cap - usage.calls_today, 0);
    return `Re-checking uses 1 ${usage.serp_provider} search (${left} of ${usage.daily_cap} left today).`;
  }

  // Fetch the results page again (skipping the cache) and compare it with the previous check.
  async function recheck(row: AnalysisRow) {
    if (!row.mock_mode && !window.confirm(`Re-check "${row.keyword}" now?

${recheckCostNote(row)}`)) return;
    setError("");
    setRechecking(true);
    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          keyword: row.keyword,
          location_name: "United States",
          language_name: "English",
          mock_mode: row.mock_mode,
          refresh: true,
        }),
      });
      const text = await res.text();
      if (!res.ok) {
        let detail = `Re-check failed (${res.status})`;
        try {
          const data = JSON.parse(text);
          if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
        } catch { /* keep generic message */ }
        throw new Error(detail);
      }
      const fresh = JSON.parse(text) as AnalysisRow;
      setRows((prev) => prev.map((r) => (r.keyword === row.keyword ? fresh : r)));
      setSelectedKeyword(fresh.keyword);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-check failed");
    } finally {
      setRechecking(false);
      refreshUsage();
    }
  }

  // Bulk results go into the same list as single analyses, so the history table, charts and exports include them.
  function addBulkResults(newRows: AnalysisRow[]) {
    if (!newRows.length) return;
    const fresh = new Set(newRows.map((r) => r.keyword));
    setRows((prev) => [...newRows, ...prev.filter((r) => !fresh.has(r.keyword))]);
    setSelectedKeyword(newRows[0].keyword);
  }

  function openFromBulk(keyword: string) {
    setSelectedKeyword(keyword);
    setBulkOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const selectedRow = useMemo(() => {
    if (!rows.length) return null;
    if (selectedKeyword) {
      return rows.find((r) => r.keyword === selectedKeyword) ?? rows[0];
    }
    return rows[0];
  }, [rows, selectedKeyword]);

  useEffect(() => {
    if (rows.length && !selectedKeyword) {
      setSelectedKeyword(rows[0].keyword);
    }
  }, [rows, selectedKeyword]);

  useEffect(() => {
    const t = window.setTimeout(() => setPageReady(true), 400);
    return () => window.clearTimeout(t);
  }, []);

  // Restore recent analyses from the backend (no API calls), and open one if the URL asks: /?open=<analysis id>.
  useEffect(() => {
    let cancelled = false;
    async function restore() {
      try {
        const openId = Number(new URLSearchParams(window.location.search).get("open")) || null;
        const res = await fetch(`${API_BASE}/history/latest?limit=20&after_id=${readClearedAfterId()}`);
        const restored: AnalysisRow[] = res.ok ? await res.json() : [];
        let opened: AnalysisRow | null = null;
        if (openId) {
          const one = await fetch(`${API_BASE}/history/${openId}`);
          if (one.ok) opened = await one.json();
          else if (!cancelled) setError("That saved analysis could not be found.");
        }
        if (cancelled) return;
        const sameKeyword = (a: AnalysisRow, b: AnalysisRow) => a.keyword.toLowerCase() === b.keyword.toLowerCase();
        const incoming = opened ? [opened, ...restored.filter((r) => !sameKeyword(r, opened!))] : restored;
        // Analyses run while this was loading stay on top.
        setRows((prev) => [...prev, ...incoming.filter((r) => !prev.some((p) => sameKeyword(p, r)))]);
        if (opened) {
          setSelectedKeyword(opened.keyword);
          window.history.replaceState(null, "", window.location.pathname);
        }
      } catch {
        /* backend unreachable: start with an empty dashboard */
      }
    }
    restore();
    return () => {
      cancelled = true;
    };
  }, []);

  function clearDashboard() {
    const lastId = Math.max(readClearedAfterId(), ...rows.map((r) => r.analysis_id ?? 0));
    writeClearedAfterId(lastId);
    setRows([]);
    setSelectedKeyword(null);
  }

  async function onAnalyze(e: FormEvent) {
    e.preventDefault();
    if (!keyword.trim()) return;
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          keyword: keyword.trim(),
          location_name: "United States",
          language_name: "English",
          mock_mode: mockMode,
          search_volume: volume.trim() === "" ? null : Number(volume)
        })
      });
      
      const text = await res.text();
      if (!res.ok) {
        let detail = `Request failed (${res.status})`;
        try {
          const data = JSON.parse(text);
          if (data.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        } catch { /* ignore */ }
        throw new Error(detail);
      }
      
      const json = JSON.parse(text) as AnalysisRow;
      setRows((prev) => [json, ...prev.filter((r) => r.keyword !== json.keyword)]);
      setSelectedKeyword(json.keyword);
      setKeyword("");
      setVolume("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
      refreshUsage();
    }
  }

  async function onDownloadReport(format: "csv" | "pdf") {
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
            report: r.report ?? null
          }))
        })
      });
      if (!res.ok) throw new Error(`Report download failed (${res.status})`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `traffic-opportunity-report.${format}`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate report");
    }
  }

  const comparisonData = useMemo(() => {
    return {
      labels: rows.map((r) => r.keyword),
      datasets: [
        {
          label: "Search Volume",
          data: rows.map((r) => (hasVolume(r) ? r.raw_volume : 0)),
          backgroundColor: "#3b82f6",
          borderRadius: 6,
        },
        {
          label: "Capturable Clicks",
          data: rows.map((r) => (hasVolume(r) ? r.capturable_clicks ?? r.adjusted_volume : 0)),
          backgroundColor: "#6366f1",
          borderRadius: 6,
        }
      ]
    };
  }, [rows]);

  if (!pageReady) return <LoadingOverlay label="Initializing Engine" sublabel="Loading analytical modules..." />;

  return (
    <div className="min-h-screen bg-slate-50/50 text-slate-900 selection:bg-indigo-100">
      {bulkOpen && (
        <BulkAnalysis
          apiBase={API_BASE}
          mockMode={mockMode}
          onClose={() => setBulkOpen(false)}
          onResults={addBulkResults}
          onOpenKeyword={openFromBulk}
        />
      )}
      {/* Sticky Header */}
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl premium-gradient text-white shadow-lg shadow-blue-500/20">
              <Zap size={20} fill="currentColor" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-slate-900">Startly <span className="text-indigo-600">Analyze</span></h1>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">Traffic Opportunity Tool</p>
            </div>
          </div>

          <form onSubmit={onAnalyze} className="flex flex-1 items-center gap-2 max-w-2xl px-8">
            <div className="relative flex-1 min-w-0 group">
              <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-indigo-500 transition-colors">
                <Search size={18} />
              </div>
              <input
                type="text"
                className="w-full h-11 pl-11 pr-44 rounded-2xl border border-slate-200 bg-slate-100/50 backdrop-blur-sm transition-all focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-sm"
                placeholder="Analyze keyword opportunity..."
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
              />
              <div className="absolute inset-y-1.5 right-1.5 flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setMockMode(!mockMode)}
                  className={cn(
                    "px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all outline-none",
                    mockMode ? "bg-amber-100 text-amber-700 shadow-sm" : "bg-slate-200 text-slate-600 hover:bg-slate-300"
                  )}
                >
                  {mockMode ? "Mock ON" : "Mock OFF"}
                </button>
                <button
                  type="submit"
                  disabled={loading || !keyword.trim()}
                  className="h-full px-4 rounded-xl premium-gradient text-white text-sm font-semibold shadow-md shadow-indigo-500/20 hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:scale-100"
                >
                  {loading ? "Analyzing..." : "Analyze"}
                </button>
              </div>
            </div>
            <input
              type="number"
              min={0}
              inputMode="numeric"
              aria-label="Monthly search volume (optional)"
              title="Monthly search volume, e.g. from Google Keyword Planner. Leave empty to use the saved or API volume."
              placeholder="Volume"
              value={volume}
              onChange={(e) => setVolume(e.target.value)}
              className="w-24 shrink-0 h-11 px-3 rounded-2xl border border-slate-200 bg-slate-100/50 text-sm text-slate-700 shadow-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
            />
          </form>

          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => setBulkOpen(true)}
              className="inline-flex items-center gap-2 h-11 px-4 rounded-2xl border border-slate-200 bg-white text-sm font-semibold text-slate-600 shadow-sm hover:border-indigo-200 hover:text-indigo-600 transition-colors"
              title="Analyze and rank a list of keywords"
            >
              <ListOrdered size={18} />
              Bulk
            </button>
            <Link
              href="/history"
              className="inline-flex items-center gap-2 h-11 px-4 rounded-2xl border border-slate-200 bg-white text-sm font-semibold text-slate-600 shadow-sm hover:border-indigo-200 hover:text-indigo-600 transition-colors"
              title="Every saved analysis"
            >
              <History size={18} />
              History
            </Link>
            <div className="h-4 w-[1px] bg-slate-200" />
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-100">
              <div className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />
              <span className="text-xs font-medium text-indigo-700">Live Engine</span>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] px-6 py-8">
        <AnimatePresence>
          {error && (
            <motion.div 
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="mb-8 p-4 rounded-2xl bg-red-50 border border-red-100 text-red-800 flex items-center gap-3"
            >
              <AlertCircle size={20} />
              <p className="text-sm font-medium">{error}</p>
              <button onClick={() => setError("")} className="ml-auto text-red-400 hover:text-red-600">
                 <XCircle size={18} />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence mode="wait">
          {!selectedRow ? (
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.05 }}
              className="flex flex-col items-center justify-center py-32 text-center"
            >
              <div className="h-20 w-20 rounded-3xl bg-indigo-50 flex items-center justify-center text-indigo-500 mb-6 font-bold shadow-inner">
                <BarChart3 size={40} />
              </div>
              <h2 className="text-2xl font-bold text-slate-900 mb-2 tracking-tight">Keyword Opportunity Engine</h2>
              <p className="text-slate-500 max-w-sm text-sm leading-relaxed">Enter a target keyword above to get deep SERP insights and true demand metrics.</p>
            </motion.div>
          ) : (
            <motion.div
              key={selectedRow.keyword}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-8"
            >
              {/* Hero Insight Card */}
              <div className={cn(
                "relative overflow-hidden rounded-[2.5rem] p-10 text-white shadow-2xl transition-all duration-500",
                selectedRow.report?.summary.saturation_status === 'success' ? "bg-gradient-to-br from-emerald-500 to-teal-600 shadow-emerald-500/30" :
                selectedRow.report?.summary.saturation_status === 'danger' ? "bg-gradient-to-br from-rose-500 to-orange-600 shadow-rose-500/30" :
                "premium-gradient shadow-indigo-500/30"
              )}>
                <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-8">
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md w-fit border border-white/20">
                      <Layers size={14} className="text-white/70" />
                      <span className="text-[10px] font-black uppercase tracking-[0.2em] text-white">Growth Verdict</span>
                    </div>
                    {selectedRow.analyzed_at && (
                      <p className="text-xs font-semibold text-white/70">
                        Analyzed {new Date(selectedRow.analyzed_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                        {selectedRow.rescored && " · older analysis, shown with today's click model"}
                      </p>
                    )}
                    <div>
                      <h2 className="text-4xl font-black tracking-tight mb-2">
                        {selectedRow.report?.summary.saturation_label ?? "Opportunity Analysis"}
                      </h2>
                      <p className="text-white/90 text-lg leading-relaxed max-w-2xl font-medium">
                        {selectedRow.report?.summary.saturation_desc ?? (
                          <>
                            Targeting <span className="text-white font-extrabold italic underline decoration-white/30 underline-offset-4">"{selectedRow.keyword}"</span> shows 
                            {selectedRow.penalty_applied ? " a marked demand disparity due to non-organic SERP saturation." : " excellent organic capture potential."}
                          </>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-col items-center justify-center h-40 w-40 rounded-full bg-white/10 backdrop-blur-2xl border border-white/20 shadow-inner group shrink-0">
                    <div className="text-[11px] uppercase font-black tracking-widest text-white/70 mb-1">Clicks kept</div>
                    <div className="text-5xl font-black transition-transform group-hover:scale-110 duration-500">{100 - (selectedRow.report?.summary.penalty_percent ?? 0)}%</div>
                    <div className="text-[10px] font-bold opacity-60 mt-1 text-center px-4">VS A PLAIN PAGE</div>
                  </div>
                </div>
                {/* Decorative Elements */}
                <div className="absolute top-0 right-0 -mr-20 -mt-20 h-80 w-80 rounded-full bg-white/10 blur-[100px]" />
                <div className="absolute bottom-0 left-0 -ml-20 -mb-20 h-80 w-80 rounded-full bg-white/10 blur-[100px]" />
              </div>

              {/* KPI Section */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <KPICard
                  icon={<BarChart3 />}
                  title="Raw Volume"
                  value={hasVolume(selectedRow) ? formatNumber(selectedRow.raw_volume) : "—"}
                  trend={volumeLabel(selectedRow.volume_source)}
                  status={hasVolume(selectedRow) ? "neutral" : "warning"}
                  description={hasVolume(selectedRow) ? "Monthly searches" : "Enter a volume to estimate clicks"}
                />
                <KPICard
                  icon={<Zap />}
                  title="Capturable Clicks"
                  value={clicksValue(selectedRow)}
                  trend={selectedRow.report?.summary.penalty_percent ? `-${selectedRow.report.summary.penalty_percent}%` : "0%"}
                  status={selectedRow.penalty_applied ? "warning" : "success"}
                  description={clicksDescription(selectedRow)}
                />
                <KPICard
                  icon={<Layers />}
                  title="Organic Share"
                  value={`${(selectedRow.saturation_score * 100).toFixed(1)}%`}
                  trend={`${selectedRow.organic_results}/${selectedRow.total_results} organic`}
                  status={selectedRow.saturation_score >= 0.8 ? "success" : selectedRow.saturation_score >= 0.5 ? "warning" : "danger"}
                  description="Page-one items that are organic links"
                />
                <KPICard
                  icon={<Info />}
                  title="Clicks per Slot"
                  value={hasVolume(selectedRow) ? (selectedRow.report?.summary.demand_per_organic_slot?.toFixed(0) ?? "—") : "—"}
                  status="success"
                  description="Average clicks per organic result"
                />
              </div>

              {/* Main Content Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Visualizations */}
                <div className="lg:col-span-2 space-y-8">
                  <div className="glass-card rounded-[2.5rem] p-10 border border-slate-200/60 shadow-xl shadow-slate-200/50">
                    {selectedRow.report?.click_model ? (
                      <ClicksByPosition model={selectedRow.report.click_model} hasVolume={hasVolume(selectedRow)} />
                    ) : (
                      <div className="py-16 text-center">
                        <Info size={32} className="mx-auto mb-4 text-slate-200" />
                        <p className="text-sm text-slate-400 font-bold">Analyze this keyword again to see clicks by position.</p>
                      </div>
                    )}
                  </div>

                  <WhatChanged
                    changes={selectedRow.changes}
                    rechecking={rechecking}
                    costNote={recheckCostNote(selectedRow)}
                    onRecheck={() => recheck(selectedRow)}
                  />

                  {/* Competitive Landscape */}
                  {rows.length > 1 && (
                    <motion.div 
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="glass-card rounded-[2.5rem] p-10 border border-slate-200/60 shadow-xl shadow-slate-200/50"
                    >
                      <div className="mb-8">
                        <h3 className="text-2xl font-black text-slate-900 tracking-tight">Market Landscape</h3>
                        <p className="text-sm text-slate-400 font-medium">Search volume vs. clicks you could actually capture</p>
                      </div>
                      <div className="h-80">
                         <Bar 
                            data={comparisonData}
                            options={{
                              responsive: true,
                              maintainAspectRatio: false,
                              plugins: { 
                                legend: { 
                                  position: 'top', 
                                  align: 'end',
                                  labels: { usePointStyle: true, pointStyle: 'circle', font: { size: 10, weight: 'bold' } } 
                                } 
                              },
                              scales: { y: { beginAtZero: true, grid: { color: "#f1f5f9" } }, x: { grid: { display: false } } }
                            }}
                         />
                      </div>
                    </motion.div>
                  )}
                </div>

                {/* Sidebar Insights */}
                <div className="space-y-8 text-white">
                  {/* Insight Panel */}
                  <div className="glass-card rounded-[2.5rem] p-8 border border-white/40 bg-white shadow-2xl shadow-slate-200/70 overflow-hidden relative">
                    <div className="relative z-10">
                      <h3 className="text-lg font-black text-slate-900 mb-8 flex items-center gap-3">
                        <div className="h-8 w-8 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-500">
                           <Zap size={18} fill="currentColor" />
                        </div>
                        Intelligence
                      </h3>
                      
                      {selectedRow.report ? (
                        <InsightsPanel sections={selectedRow.report.sections} />
                      ) : (
                        <div className="py-16 text-center">
                          <Info size={32} className="mx-auto mb-4 text-slate-200" />
                          <p className="text-sm text-slate-400 font-bold px-8">Analysis pending data retrieval.</p>
                        </div>
                      )}

                      <div className="mt-12 pt-10 border-t border-slate-100">
                        <h3 className="text-lg font-black text-slate-900 mb-8 flex items-center gap-3">
                          <div className="h-8 w-8 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-500">
                             <PieChart size={18} fill="currentColor" />
                          </div>
                          SERP Mix
                        </h3>
                        <div className="h-64 relative">
                          <Doughnut 
                            data={{
                              labels: Object.keys(selectedRow.report?.summary.type_breakdown ?? {}),
                              datasets: [{
                                data: Object.values(selectedRow.report?.summary.type_breakdown ?? {}),
                                backgroundColor: [
                                  '#6366f1', '#818cf8', '#a5b4fc', '#c7d2fe', '#e0e7ff', '#f0f9ff'
                                ],
                                borderWidth: 0
                              }]
                            }}
                            options={{
                              cutout: '82%',
                              responsive: true,
                              maintainAspectRatio: false,
                              plugins: { legend: { display: false } }
                            }}
                          />
                          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                             <div className="text-4xl font-black text-indigo-600">{selectedRow.total_results}</div>
                             <div className="text-[9px] font-black text-slate-400 uppercase tracking-widest mt-1">SERP ITEMS</div>
                          </div>
                        </div>
                        <div className="mt-8 space-y-2">
                           {Object.entries(selectedRow.report?.summary.type_breakdown ?? {}).map(([type, count], i) => (
                             <div key={type} className="flex items-center justify-between p-3 rounded-2xl hover:bg-slate-50 transition-colors border border-transparent hover:border-slate-100 group">
                               <div className="flex items-center gap-3">
                                 <div className="h-2 w-2 rounded-full transition-transform group-hover:scale-150" style={{ backgroundColor: ['#6366f1', '#818cf8', '#a5b4fc', '#c7d2fe', '#e0e7ff', '#f0f9ff'][i % 6] }} />
                                 <span className="text-xs font-bold text-slate-500 capitalize">{type.replace(/_/g, ' ')}</span>
                               </div>
                               <span className="text-xs font-black text-slate-900">{count}</span>
                             </div>
                           ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="grid grid-cols-1 gap-4">
                    <button 
                      onClick={() => onDownloadReport("pdf")}
                      disabled={!rows.length || loading}
                      className="flex items-center justify-center gap-3 w-full py-5 rounded-[2rem] bg-slate-900 text-white font-black text-sm transition-all hover:bg-slate-800 hover:scale-[1.02] active:scale-[0.98] shadow-lg shadow-slate-900/20 disabled:opacity-50"
                    >
                      <Download size={20} />
                      Export PDF Report
                    </button>
                    <button 
                      onClick={() => onDownloadReport("csv")}
                      disabled={!rows.length || loading}
                      className="flex items-center justify-center gap-3 w-full py-5 rounded-[2rem] border-2 border-slate-100 bg-white text-slate-600 font-black text-sm transition-all hover:bg-slate-50 hover:border-slate-200 disabled:opacity-50"
                    >
                      <FileText size={20} />
                      CSV Dataset
                    </button>
                  </div>
                </div>
              </div>

              {/* Data History Table */}
              <div className="glass-card rounded-[2.5rem] overflow-hidden border border-slate-200/60 shadow-xl shadow-slate-200/40">
                <div className="px-10 py-8 border-b border-slate-100 flex items-center justify-between bg-white">
                  <div>
                    <h3 className="text-2xl font-black text-slate-900 tracking-tight">Intelligence Logs</h3>
                    <p className="text-sm text-slate-400 font-medium">Historical keyword performance snapshots</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Link
                      href="/history"
                      className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-50 border border-slate-100 hover:border-indigo-200 transition-colors"
                      title="See every saved analysis"
                    >
                      <History size={16} className="text-slate-400" />
                      <span className="text-xs font-black text-slate-500 uppercase tracking-widest">{rows.length} on dashboard</span>
                    </Link>
                    <button
                      type="button"
                      onClick={clearDashboard}
                      className="px-4 py-2 rounded-xl border border-slate-100 text-xs font-black uppercase tracking-widest text-slate-400 hover:text-rose-600 hover:border-rose-100 transition-colors"
                      title="Remove these from the dashboard. They stay in History."
                    >
                      Clear
                    </button>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="bg-slate-50/50 text-[11px] font-black text-slate-400 uppercase tracking-widest">
                        <th className="px-10 py-5">Keyword Profile</th>
                        <th className="px-10 py-5 text-right">Volume</th>
                        <th className="px-10 py-5 text-right">Clicks</th>
                        <th className="px-10 py-5 text-center">Organic Share</th>
                        <th className="px-10 py-5 text-center">Click Access</th>
                        <th className="px-10 py-5 text-right">Metrics</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {rows.map((row) => (
                        <tr 
                          key={row.keyword} 
                          onClick={() => setSelectedKeyword(row.keyword)}
                          className={cn(
                            "group cursor-pointer transition-all hover:bg-indigo-50/30",
                            selectedRow.keyword === row.keyword ? "bg-indigo-50/20" : ""
                          )}
                        >
                          <td className="px-10 py-6">
                            <div className="flex items-center gap-4">
                              <div className={cn(
                                "h-10 w-10 rounded-2xl flex items-center justify-center transition-all shadow-sm ring-4 ring-transparent group-hover:ring-indigo-50",
                                selectedRow.keyword === row.keyword ? "bg-indigo-500 text-white shadow-indigo-200" : "bg-white border border-slate-100 text-slate-400"
                              )}>
                                <Zap size={16} fill={selectedRow.keyword === row.keyword ? "currentColor" : "none"} />
                              </div>
                              <span className="font-extrabold text-slate-900 text-base">{row.keyword}</span>
                            </div>
                          </td>
                          <td className="px-10 py-6 text-right font-bold text-slate-500 tabular-nums">
                            {hasVolume(row) ? formatNumber(row.raw_volume) : "—"}
                            <div className="text-[10px] font-semibold text-slate-400">{volumeLabel(row.volume_source)}</div>
                          </td>
                          <td className="px-10 py-6 text-right font-black text-slate-900 tabular-nums">
                            {clicksValue(row)}
                            {hasVolume(row) && row.capturable_clicks_low != null && row.capturable_clicks_low !== row.capturable_clicks_high && (
                              <div className="text-[10px] font-semibold text-slate-400">
                                {formatNumber(row.capturable_clicks_low)}–{formatNumber(row.capturable_clicks_high ?? 0)}
                              </div>
                            )}
                          </td>
                          <td className="px-10 py-6 text-center">
                            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100/50 text-xs font-black text-slate-600 border border-slate-100">
                              {(row.saturation_score * 100).toFixed(0)}%
                            </div>
                          </td>
                          <td className="px-10 py-6 text-center">
                            <div className={cn(
                              "inline-flex items-center px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-wider",
                              clickTier(row).className
                            )}>
                              {clickTier(row).label}
                            </div>
                          </td>
                          <td className="px-10 py-6 text-right">
                             <button className="h-10 w-10 rounded-xl hover:bg-slate-100 flex items-center justify-center text-slate-300 hover:text-slate-600 transition-colors">
                                <MoreHorizontal size={20} />
                             </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <footer className="mx-auto max-w-[1400px] px-10 py-20 mt-20 border-t border-slate-200/60 bg-white/50 backdrop-blur-sm rounded-t-[3rem]">
        <div className="flex flex-col md:flex-row justify-between items-center gap-10">
          <div className="space-y-4 max-w-sm">
             <div className="flex items-center gap-3">
               <div className="h-8 w-8 rounded-xl premium-gradient flex items-center justify-center text-white">
                  <Zap size={16} fill="currentColor" />
               </div>
               <span className="font-black text-xl tracking-tighter">STARTLY <span className="text-indigo-600 underline decoration-indigo-200 underline-offset-4">ANALYZE</span></span>
             </div>
             <p className="text-slate-400 text-xs font-semibold leading-relaxed">Advanced keyword intelligence platform for elite SEO teams. Driven by real-time SERP data and proprietary traffic models.</p>
          </div>
          <div className="flex flex-col items-center md:items-end gap-6 text-center md:text-right">
             <p className="text-slate-400 text-[10px] font-bold tracking-widest uppercase">© 2026 STARTLY WORLDWIDE ANALYTICS GROUP</p>
             <div className="flex items-center gap-8">
               <a href="https://github.com/Nandhagopal2912/Startly-1-1/blob/main/README.md" target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-indigo-600 transition-colors text-xs font-black uppercase tracking-widest">README</a>
               <a href="https://github.com/Nandhagopal2912/Startly-1-1/blob/main/ARCHITECTURE.md" target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-indigo-600 transition-colors text-xs font-black uppercase tracking-widest">Architecture</a>
               <a href="#" className="text-slate-500 hover:text-indigo-600 transition-colors text-xs font-black uppercase tracking-widest">Connect API</a>
             </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

function KPICard({
  icon, 
  title, 
  value, 
  trend, 
  status, 
  description 
}: { 
  icon: React.ReactNode; 
  title: string; 
  value: string; 
  trend?: string;
  status: 'success' | 'warning' | 'danger' | 'neutral';
  description: string;
}) {
  const statusStyles = {
    success: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    warning: 'bg-amber-50 text-amber-600 border-amber-100',
    danger: 'bg-rose-50 text-rose-600 border-rose-100',
    neutral: 'bg-indigo-50 text-indigo-600 border-indigo-100'
  };

  const trendIcon = trend?.startsWith('+') ? <TrendingUp size={12} /> : trend?.startsWith('-') ? <TrendingDown size={12} /> : null;

  return (
    <div className="glass-card rounded-[2.5rem] p-8 border border-slate-200/60 bg-white hover:scale-[1.03] transition-all cursor-default group shadow-lg hover:shadow-2xl shadow-slate-200/50">
      <div className="flex items-center justify-between mb-6">
        <div className={cn("h-12 w-12 rounded-2xl flex items-center justify-center transition-transform group-hover:rotate-12 group-hover:scale-110 border shadow-sm", statusStyles[status])}>
          {icon}
        </div>
        {trend && (
          <div className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-black transition-all",
            trend.startsWith('+') && status === 'success' ? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/30" :
            trend.startsWith('-') && status === 'warning' ? "bg-rose-500 text-white shadow-lg shadow-rose-500/30" :
            "bg-slate-100 text-slate-500 border border-slate-200"
          )}>
            {trendIcon} {trend}
          </div>
        )}
      </div>
      <div className="space-y-1.5">
        <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">{title}</h4>
        <div className="text-4xl font-black text-slate-900 tracking-tight tabular-nums overflow-hidden text-ellipsis whitespace-nowrap">{value}</div>
        <p className="text-[11px] text-slate-400 font-bold group-hover:text-slate-500 transition-colors uppercase tracking-wider">{description}</p>
      </div>
    </div>
  );
}
