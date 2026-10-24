"use client";

import { FormEvent, useEffect, useState } from "react";
import { Check, CircleHelp, Loader2, Pencil, ThumbsDown, ThumbsUp, TrendingUp, X } from "lucide-react";
import { cn, formatNumber } from "../lib/utils";
import { type AnalysisRow, hasVolume, rowCountry, volumeLabel } from "../lib/analysis";

const TONES = {
  good: { badge: "bg-emerald-100 text-emerald-800", icon: <ThumbsUp size={16} />, ring: "border-emerald-200" },
  neutral: { badge: "bg-amber-100 text-amber-800", icon: <TrendingUp size={16} />, ring: "border-amber-200" },
  bad: { badge: "bg-rose-100 text-rose-800", icon: <ThumbsDown size={16} />, ring: "border-rose-200" },
  unknown: { badge: "bg-slate-100 text-slate-700", icon: <CircleHelp size={16} />, ring: "border-slate-200" },
};

export function VerdictHero({
  row,
  savingVolume,
  onSaveVolume,
}: {
  row: AnalysisRow;
  savingVolume: boolean;
  onSaveVolume: (volume: number) => Promise<void>;
}) {
  const verdict = row.report?.verdict;
  const tone = TONES[verdict?.tone ?? "unknown"];
  const known = hasVolume(row);
  const low = row.capturable_clicks_low, high = row.capturable_clicks_high;
  const loss = row.report?.summary.penalty_percent ?? 0;

  return (
    <section className={cn("rounded-3xl border bg-white p-6 shadow-sm sm:p-8", tone.ring)}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs text-slate-500">
            {rowCountry(row)}
            {row.provider && ` · ${row.provider}`}
            {row.analyzed_at && ` · analyzed ${new Date(row.analyzed_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}`}
            {row.mock_mode && " · mock data"}
          </p>
          <h2 className="mt-1 break-words text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{row.keyword}</h2>
        </div>
        {verdict && (
          <span className={cn("inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold", tone.badge)}>
            {tone.icon} {verdict.label}
          </span>
        )}
      </div>

      {verdict && <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-600">{verdict.reason}</p>}
      {row.rescored && (
        <p className="mt-2 text-xs text-amber-700">Older analysis: numbers are recalculated with today&apos;s click model.</p>
      )}

      <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-5 border-t border-slate-100 pt-6 md:grid-cols-4 2xl:grid-cols-5">
        <div className="col-span-2 md:col-span-4 2xl:col-span-1">
          <dt className="text-xs font-medium text-slate-500">Capturable clicks / month</dt>
          <dd className="mt-1 text-3xl font-bold tabular-nums text-slate-900">
            {known && row.capturable_clicks != null ? formatNumber(row.capturable_clicks) : "—"}
          </dd>
          <dd className="text-xs text-slate-500">
            {known && low != null && high != null && low !== high
              ? `range ${formatNumber(low)}–${formatNumber(high)}`
              : !known
                ? `${row.report?.summary.organic_ctr_total?.toFixed(1) ?? "—"}% of searches click organic`
                : "organic, page one"}
          </dd>
        </div>
        <Stat label="#1 ranking worth" value={verdict?.top1_clicks} suffix="clicks" />
        <Stat label="Top 3 combined" value={verdict?.top3_clicks} suffix="clicks" />
        <div>
          <dt className="text-xs font-medium text-slate-500">Clicks lost to SERP features</dt>
          <dd className={cn("mt-1 text-xl font-semibold tabular-nums", loss >= 50 ? "text-rose-600" : loss >= 25 ? "text-amber-600" : "text-emerald-600")}>
            {loss}%
          </dd>
          <dd className="text-xs text-slate-500">vs a page with only organic links</dd>
        </div>
        <VolumeField row={row} saving={savingVolume} onSave={onSaveVolume} />
      </dl>
    </section>
  );
}

function Stat({ label, value, suffix }: { label: string; value: number | null | undefined; suffix: string }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd className="mt-1 text-xl font-semibold tabular-nums text-slate-900">{value != null ? formatNumber(value) : "—"}</dd>
      <dd className="text-xs text-slate-500">{value != null ? `${suffix} / month` : "needs volume"}</dd>
    </div>
  );
}

function VolumeField({ row, saving, onSave }: { row: AnalysisRow; saving: boolean; onSave: (v: number) => Promise<void> }) {
  const known = hasVolume(row);
  const [editing, setEditing] = useState(!known);
  const [value, setValue] = useState(known ? String(row.raw_volume) : "");

  // Switching keywords resets the field.
  useEffect(() => {
    setEditing(!hasVolume(row));
    setValue(hasVolume(row) ? String(row.raw_volume) : "");
  }, [row.keyword, row.raw_volume, row.volume_source]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(e: FormEvent) {
    e.preventDefault();
    const n = Number(value.replace(/[,\s]/g, ""));
    if (!Number.isFinite(n) || n < 0) return;
    await onSave(n);
    setEditing(false);
  }

  return (
    <div>
      <dt className="text-xs font-medium text-slate-500">Monthly searches</dt>
      {editing ? (
        <form onSubmit={submit} className="mt-1 flex items-center gap-1">
          <input
            autoFocus={known}
            inputMode="numeric"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="e.g. 5000"
            aria-label="Monthly search volume"
            className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm tabular-nums focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          />
          <button type="submit" disabled={saving || !value.trim()} className="rounded-lg bg-indigo-600 p-1.5 text-white disabled:opacity-40" aria-label="Save volume">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
          </button>
          {known && (
            <button type="button" onClick={() => setEditing(false)} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100" aria-label="Cancel">
              <X size={14} />
            </button>
          )}
        </form>
      ) : (
        <dd className="mt-1 flex items-center gap-1.5">
          <span className="text-xl font-semibold tabular-nums text-slate-900">{formatNumber(row.raw_volume)}</span>
          <button type="button" onClick={() => setEditing(true)} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600" aria-label="Edit volume">
            <Pencil size={13} />
          </button>
        </dd>
      )}
      <dd className="text-xs text-slate-500">{known ? volumeLabel(row.volume_source) : "Free to add: no API call"}</dd>
    </div>
  );
}
