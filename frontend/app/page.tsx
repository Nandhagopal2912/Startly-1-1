"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip
} from "chart.js";
import { Bar } from "react-chartjs-2";
import { AnalyzeReportPanel, type FullReport } from "../components/AnalyzeReport";
import { LoadingOverlay } from "../components/LoadingOverlay";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

type AnalysisRow = {
  keyword: string;
  raw_volume: number;
  adjusted_volume: number;
  saturation_score: number;
  organic_results: number;
  total_results: number;
  penalty_applied: boolean;
  source: string;
  mock_mode: boolean;
  report?: FullReport;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function HomePage() {
  const [keyword, setKeyword] = useState("");
  const [mockMode, setMockMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [pageReady, setPageReady] = useState(false);
  const [error, setError] = useState("");
  const [rows, setRows] = useState<AnalysisRow[]>([]);
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);

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
    const minMs = 420;
    const t = window.setTimeout(() => setPageReady(true), minMs);
    return () => window.clearTimeout(t);
  }, []);

  const chartData = useMemo(() => {
    return {
      labels: rows.map((r) => r.keyword),
      datasets: [
        {
          label: "Raw volume",
          data: rows.map((r) => r.raw_volume),
          backgroundColor: "rgba(59, 130, 246, 0.6)"
        },
        {
          label: "Adjusted (true demand)",
          data: rows.map((r) => r.adjusted_volume),
          backgroundColor: "rgba(16, 185, 129, 0.7)"
        },
        {
          label: "Organic slots (supply)",
          data: rows.map((r) => r.organic_results),
          backgroundColor: "rgba(245, 158, 11, 0.7)"
        }
      ]
    };
  }, [rows]);

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
          mock_mode: mockMode
        })
      });
      const text = await res.text();
      if (!res.ok) {
        let detail = `Request failed (${res.status})`;
        try {
          const data = JSON.parse(text) as { detail?: unknown };
          if (data.detail != null) {
            detail =
              typeof data.detail === "string"
                ? data.detail
                : Array.isArray(data.detail)
                  ? data.detail
                      .map((x) => (typeof x === "object" && x !== null ? JSON.stringify(x) : String(x)))
                      .join(" ")
                  : String(data.detail);
          }
        } catch {
          if (text.trim()) detail = text.trim().slice(0, 500);
        }
        throw new Error(detail);
      }
      const json = JSON.parse(text) as AnalysisRow;
      setRows((prev) => [json, ...prev.filter((r) => r.keyword !== json.keyword)]);
      setSelectedKeyword(json.keyword);
      setKeyword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function onDownloadReport(format: "csv" | "pdf") {
    if (!rows.length) return;
    const res = await fetch(`${API_BASE}/report`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        format,
        rows: rows.map((r) => ({
          keyword: r.keyword,
          raw_volume: r.raw_volume,
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
    if (!res.ok) {
      setError(`Report download failed with status ${res.status}`);
      return;
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = format === "csv" ? "traffic-opportunity-report.csv" : "traffic-opportunity-report.pdf";
    link.click();
    window.URL.revokeObjectURL(url);
  }

  if (!pageReady) {
    return <LoadingOverlay label="Opening app" sublabel="Traffic Opportunity Tool" />;
  }

  return (
    <main className="animate-page-enter mx-auto max-w-6xl p-6">
      {loading ? (
        <LoadingOverlay
          label="Analyzing keyword"
          sublabel="Calling the API or reading cache — this may take a few seconds."
        />
      ) : null}
      <h1 className="mb-2 text-3xl font-bold text-slate-900">Traffic Opportunity Tool</h1>
      <p className="mb-6 max-w-3xl text-slate-600">
        Each analysis produces a full report: KPIs, charts for demand vs supply and SERP composition, and
        step-by-step explanations with the underlying numbers. Live mode uses DataForSEO{" "}
        <strong className="font-medium text-slate-700">Standard (Regular) Organic</strong> — set{" "}
        <code className="rounded bg-slate-200/80 px-1 text-xs">DATAFORSEO_EMAIL</code> and{" "}
        <code className="rounded bg-slate-200/80 px-1 text-xs">DATAFORSEO_PASSWORD</code> in{" "}
        <code className="rounded bg-slate-200/80 px-1 text-xs">backend/.env</code>.
      </p>

      <form
        onSubmit={onAnalyze}
        className="mb-6 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-6"
      >
        <input
          className="col-span-4 rounded-lg border border-slate-300 p-2.5 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder="Enter keyword"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <label className="col-span-1 flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={mockMode}
            onChange={(e) => setMockMode(e.target.checked)}
            className="rounded border-slate-300"
          />
          Mock mode
        </label>
        <button
          disabled={loading}
          className="col-span-1 rounded-lg bg-blue-600 px-3 py-2.5 font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </form>

      <div className="mb-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onDownloadReport("csv")}
          disabled={!rows.length}
          className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          Download CSV
        </button>
        <button
          type="button"
          onClick={() => onDownloadReport("pdf")}
          disabled={!rows.length}
          className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          Download PDF
        </button>
      </div>

      {error && (
        <p className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800">{error}</p>
      )}

      {selectedRow?.report && (
        <AnalyzeReportPanel
          keyword={selectedRow.keyword}
          source={selectedRow.source}
          mock_mode={selectedRow.mock_mode}
          report={selectedRow.report}
        />
      )}

      {selectedRow && !selectedRow.report && (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          This result has no detailed report payload. Run analyze again with the latest API.
        </div>
      )}

      {rows.length > 0 && (
        <section className="mb-8 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold text-slate-900">Compare keywords</h2>
          <div className="h-72">
            <Bar
              data={chartData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { position: "top" },
                  tooltip: { mode: "index", intersect: false }
                },
                scales: { y: { beginAtZero: true } }
              }}
            />
          </div>
        </section>
      )}

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 bg-slate-50 px-4 py-3">
          <h2 className="font-semibold text-slate-900">History</h2>
          <p className="text-xs text-slate-600">Click a row to open its detailed report above.</p>
        </div>
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-slate-100/80">
            <tr>
              <th className="p-3">Keyword</th>
              <th className="p-3">Raw volume</th>
              <th className="p-3">Adjusted</th>
              <th className="p-3">Saturation</th>
              <th className="p-3">True demand / supply</th>
              <th className="p-3">Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.keyword}
                onClick={() => setSelectedKeyword(row.keyword)}
                className={`cursor-pointer border-t border-slate-200 transition-colors hover:bg-slate-50 ${
                  selectedRow?.keyword === row.keyword ? "bg-blue-50/80" : ""
                }`}
              >
                <td className="p-3 font-medium">{row.keyword}</td>
                <td className="p-3 tabular-nums">{row.raw_volume.toLocaleString()}</td>
                <td className="p-3 tabular-nums">{row.adjusted_volume.toLocaleString()}</td>
                <td className="p-3 tabular-nums">{(row.saturation_score * 100).toFixed(1)}%</td>
                <td className="p-3 tabular-nums">
                  {row.adjusted_volume.toFixed(0)} / {row.organic_results} organic
                </td>
                <td className="p-3 text-slate-600">
                  {row.source} {row.mock_mode ? "(mock)" : "(live)"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
