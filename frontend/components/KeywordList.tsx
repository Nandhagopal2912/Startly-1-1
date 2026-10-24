"use client";

import { Download, FileText, Trash2, X } from "lucide-react";
import { cn, formatNumber } from "../lib/utils";
import { type AnalysisRow, type SortKey, clickTier, hasVolume, sortRows } from "../lib/analysis";

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
  onExport: (format: "csv" | "pdf") => void;
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
        <button
          type="button"
          onClick={() => onExport("csv")}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          <FileText size={14} /> CSV
        </button>
        <button
          type="button"
          onClick={() => onExport("pdf")}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          <Download size={14} /> PDF
        </button>
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
