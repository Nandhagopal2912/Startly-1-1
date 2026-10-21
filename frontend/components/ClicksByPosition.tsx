"use client";

import { Bar } from "react-chartjs-2";
import type { ChartData, ChartOptions } from "chart.js";
import { ExternalLink } from "lucide-react";
import { cn, formatNumber } from "../lib/utils";
import type { ClickModel } from "./AnalyzeReport";

const CONFIDENCE_STYLES = {
  high: "bg-emerald-50 text-emerald-700 border-emerald-100",
  medium: "bg-amber-50 text-amber-700 border-amber-100",
  low: "bg-rose-50 text-rose-700 border-rose-100",
};

export function ClicksByPosition({ model, hasVolume }: { model: ClickModel; hasVolume: boolean }) {
  const positions = model.positions;
  // Without a search volume, plot the share of searches (%) instead of click counts.
  const mid = positions.map((p) => (hasVolume ? p.clicks ?? 0 : p.ctr));
  const range = positions.map((p) =>
    hasVolume ? [p.clicks_low ?? 0, p.clicks_high ?? 0] : [p.ctr_low, p.ctr_high]
  ) as [number, number][];
  const hasRange = range.some(([lo, hi]) => hi > lo);
  const fmt = (v: number) => (hasVolume ? `${formatNumber(v)} clicks` : `${v.toFixed(2)}%`);

  const data: ChartData<"bar", (number | [number, number])[], string> = {
    labels: positions.map((p) => `#${p.position}`),
    datasets: [
      {
        label: "Estimate",
        data: mid,
        backgroundColor: "#6366f1",
        borderRadius: 10,
        barPercentage: 0.55,
        order: 1,
      },
      ...(hasRange
        ? [{
            label: "Range",
            data: range,
            backgroundColor: "rgba(99, 102, 241, 0.15)",
            borderColor: "rgba(99, 102, 241, 0.45)",
            borderWidth: 1,
            borderRadius: 10,
            barPercentage: 0.8,
            order: 2,
          }]
        : []),
    ],
  };

  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    datasets: { bar: { grouped: false } },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const raw = ctx.raw as number | [number, number];
            return Array.isArray(raw)
              ? `Range: ${fmt(raw[0])} – ${fmt(raw[1])}`
              : `Estimate: ${fmt(raw)}`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: "#f1f5f9" },
        border: { display: false },
        ticks: {
          font: { size: 10, weight: "bold" },
          color: "#94a3b8",
          callback: (v) => (hasVolume ? formatNumber(Number(v)) : `${v}%`),
        },
      },
      x: { grid: { display: false }, border: { display: false }, ticks: { font: { size: 11, weight: "bold" }, color: "#64748b" } },
    },
  };

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4 mb-8">
        <div>
          <h3 className="text-2xl font-black text-slate-900 tracking-tight">Clicks by Position</h3>
          <p className="text-sm text-slate-400 font-medium">
            {hasVolume
              ? "Estimated monthly organic clicks if you rank at each position"
              : "Share of searches clicking each position. Enter a volume to see clicks"}
          </p>
        </div>
        <div className="flex gap-2 p-1.5 rounded-2xl bg-slate-50 border border-slate-100">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white shadow-sm text-[10px] font-black text-slate-600">
            <div className="h-2 w-2 rounded-full bg-indigo-500" /> ESTIMATE
          </div>
          {hasRange && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-black text-slate-400">
              <div className="h-2 w-2 rounded-full bg-indigo-200 border border-indigo-300" /> RANGE
            </div>
          )}
        </div>
      </div>

      {positions.length ? (
        <div className="h-[340px]">
          <Bar data={data} options={options} />
        </div>
      ) : (
        <p className="py-16 text-center text-sm font-bold text-slate-400">No organic results on page one.</p>
      )}

      <div className="mt-8 pt-8 border-t border-slate-100">
        <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 mb-4">What lowers clicks here</h4>
        {model.factors.length ? (
          <ul className="space-y-2">
            {model.factors.map((f) => (
              <li key={f.feature} className="flex flex-wrap items-center gap-3 text-sm">
                <span className="font-extrabold text-slate-800">{f.label}</span>
                <span className="font-black text-rose-600 tabular-nums">{f.position_1_effect_percent}% at #1</span>
                <span className={cn("px-2 py-0.5 rounded-full border text-[10px] font-black uppercase", CONFIDENCE_STYLES[f.confidence])}>
                  {f.confidence} confidence
                </span>
                <a
                  href={f.url}
                  target="_blank"
                  rel="noreferrer"
                  title={f.source}
                  className="inline-flex items-center gap-1 text-xs font-bold text-slate-400 hover:text-indigo-600"
                >
                  source <ExternalLink size={12} />
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm font-medium text-slate-500">No features that measurably reduce organic clicks.</p>
        )}
        {model.neutral_features.length > 0 && (
          <p className="mt-3 text-xs font-medium text-slate-400">
            Also present, with no measurable effect: {model.neutral_features.map((t) => t.replace(/_/g, " ")).join(", ")}.
          </p>
        )}
        <p className="mt-3 text-xs font-medium text-slate-400">
          Baseline click rates:{" "}
          <a href={model.baseline_source.url} target="_blank" rel="noreferrer" className="underline hover:text-indigo-600">
            {model.baseline_source.name}
          </a>
        </p>
      </div>
    </div>
  );
}
