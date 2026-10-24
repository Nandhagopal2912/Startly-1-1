"use client";

import type { JSX } from "react";
import { ChevronDown, Download, FileText, Table2, Trash2, X } from "lucide-react";
import { cn, formatNumber } from "../lib/utils";
import { type AnalysisRow, type SortKey, clickTier, hasVolume, sortRows } from "../lib/analysis";

export type ExportFormat = "pdf" | "csv" | "rankings";
export type ExportScope = "all" | "selected";

const TIER_DOTS: Record<string, string> = {
  Open: "bg-emerald-500",
  Contested: "bg-amber-500",
  "Click-hostile": "bg-rose-500",
};

export function KeywordList({
  rows,
  selectedKeyword,
  sortKey,
  onSort,
  onSelect,
  onRemove,
  onClear,
  onExport,
}: {
  rows: AnalysisRow[];
  selectedKeyword: string | null;
  sortKey: SortKey;
  onSort: (key: SortKey) => void;
  onSelect: (keyword: string) => void;
  onRemove: (keyword: string) => void;
  onClear: () => void;
  onExport: (format: ExportFormat, scope: ExportScope) => void;
}) {
  const sorted = sortRows(rows, sortKey);
  return (
    <div className="rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-5 py-4">
        <h2 className="text-sm font-semibold text-slate-900">
          Keywords <span className="font-normal text-slate-400">({rows.length})</span>
        </h2>
        <label className="flex items-center gap-1.5 text-xs text-slate-500">
          Sort
          <select
            value={sortKey}
            onChange={(e) => onSort(e.target.value as SortKey)}
            className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          >
            <option value="clicks">Most clicks</option>
            <option value="volume">Most volume</option>
            <option value="recent">Most recent</option>
            <option value="name">A–Z</option>
          </select>
        </label>
      </div>

      <ul className="max-h-[60vh] overflow-y-auto py-2">
        {sorted.map((row) => {
          const selected = row.keyword === selectedKeyword;
          const tier = clickTier(row);
          return (
            <li key={row.keyword} className="group relative">
              <button
                type="button"
                onClick={() => onSelect(row.keyword)}
                className={cn(
                  "flex w-full items-center gap-3 px-5 py-2.5 pr-10 text-left transition-colors",
                  selected ? "bg-indigo-50" : "hover:bg-slate-50"
                )}
                aria-current={selected ? "true" : undefined}
              >
                <span className={cn("h-2 w-2 shrink-0 rounded-full", TIER_DOTS[tier.label] ?? "bg-slate-300")} title={tier.label} />
                <span className="min-w-0 flex-1">
                  <span className={cn("block truncate text-sm", selected ? "font-semibold text-indigo-900" : "font-medium text-slate-800")}>
                    {row.keyword}
                    {row.own_key && (
                      <span className="ml-1.5 rounded bg-emerald-50 px-1.5 py-0.5 align-middle text-[10px] font-semibold text-emerald-700" title="Analyzed with your key, saved in this browser">
                        yours
                      </span>
                    )}
                  </span>
                  <span className="block text-xs text-slate-400">
                    {hasVolume(row) && row.capturable_clicks != null
                      ? `${formatNumber(row.capturable_clicks)} clicks · ${formatNumber(row.raw_volume)} searches`
                      : `${row.report?.summary.organic_ctr_total?.toFixed(1) ?? "—"}% CTR · no volume`}
                  </span>
                </span>
              </button>
              <button
                type="button"
                onClick={() => onRemove(row.keyword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-300 opacity-0 transition-opacity hover:bg-slate-100 hover:text-slate-600 focus:opacity-100 group-hover:opacity-100"
                aria-label={`Remove ${row.keyword} from the dashboard`}
                title="Remove from dashboard (stays in History)"
              >
                <X size={14} />
              </button>
            </li>
          );
        })}
      </ul>

      <div className="flex items-center gap-2 border-t border-slate-100 px-5 py-3">
        <ExportMenu count={rows.length} selected={selectedKeyword} onExport={onExport} />
        <button
          type="button"
          onClick={onClear}
          className="ml-auto inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-400 hover:bg-rose-50 hover:text-rose-600"
          title="Remove all from the dashboard. They stay in History."
        >
          <Trash2 size={14} /> Clear
        </button>
      </div>
    </div>
  );
}

function ExportMenu({
  count,
  selected,
  onExport,
}: {
  count: number;
  selected: string | null;
  onExport: (format: ExportFormat, scope: ExportScope) => void;
}) {
  const options: { format: ExportFormat; scope: ExportScope; icon: JSX.Element; title: string; detail: string }[] = [
    { format: "pdf", scope: "all", icon: <Download size={15} />, title: `PDF report: all ${count} keywords`, detail: "Ranked summary, then a page per keyword" },
    ...(selected
      ? [{ format: "pdf" as const, scope: "selected" as const, icon: <Download size={15} />, title: "PDF report: this keyword", detail: selected }]
      : []),
    { format: "csv", scope: "all", icon: <FileText size={15} />, title: "CSV: keywords", detail: "One row per keyword, for spreadsheets" },
    { format: "rankings", scope: "all", icon: <Table2 size={15} />, title: "CSV: page-one rankings", detail: "Each keyword's ranking sites and their clicks" },
  ];
  return (
    <details className="group relative">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 [&::-webkit-details-marker]:hidden">
        <Download size={14} /> Export <ChevronDown size={13} className="transition-transform group-open:rotate-180" />
      </summary>
      <div className="absolute bottom-full left-0 z-20 mb-2 w-72 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl">
        {options.map((o) => (
          <button
            key={`${o.format}-${o.scope}`}
            type="button"
            onClick={(e) => {
              (e.currentTarget.closest("details") as HTMLDetailsElement | null)?.removeAttribute("open");
              onExport(o.format, o.scope);
            }}
            className="flex w-full items-start gap-3 rounded-xl px-3 py-2 text-left hover:bg-slate-50"
          >
            <span className="mt-0.5 text-slate-400">{o.icon}</span>
            <span className="min-w-0">
              <span className="block text-sm font-medium text-slate-800">{o.title}</span>
              <span className="block truncate text-xs text-slate-500">{o.detail}</span>
            </span>
          </button>
        ))}
      </div>
    </details>
  );
}
