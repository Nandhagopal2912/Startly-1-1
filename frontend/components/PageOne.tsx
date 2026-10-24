"use client";

import { ExternalLink } from "lucide-react";
import { formatNumber } from "../lib/utils";
import { type AnalysisRow, hasVolume } from "../lib/analysis";

function featureName(type: string) {
  return type.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

export function PageOne({ row }: { row: AnalysisRow }) {
  const model = row.report?.click_model;
  const known = hasVolume(row);
  // Older saved analyses have no domains; fall back to the position estimates alone.
  const rows =
    row.report?.page_one ??
    (model?.positions ?? []).map((p) => ({ ...p, domain: null as string | null }));
  const value = (r: (typeof rows)[number]) => (known ? r.clicks ?? 0 : r.ctr ?? 0);
  const max = Math.max(1, ...rows.map(value));

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <h3 className="text-base font-semibold text-slate-900">Page one right now</h3>
      <p className="mt-0.5 text-xs text-slate-500">
        Who ranks, and {known ? "the monthly clicks each position should get" : "the share of searches each position should get"}
      </p>

      {(model?.factors.length || model?.neutral_features.length) ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {model?.factors.map((f) => (
            <span key={f.feature} className="rounded-full bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700" title={f.source}>
              {f.label} · {f.position_1_effect_percent}% at #1
            </span>
          ))}
          {model?.neutral_features.map((t) => (
            <span key={t} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600" title="Present, no measurable effect on organic clicks">
              {featureName(t)}
            </span>
          ))}
        </div>
      ) : null}

      {rows.length === 0 ? (
        <p className="mt-6 text-sm text-slate-500">No organic results on page one.</p>
      ) : (
        <table className="mt-5 w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-400">
              <th className="w-8 pb-2 font-medium">#</th>
              <th className="pb-2 font-medium">Site</th>
              <th className="w-[45%] pb-2 text-right font-medium">{known ? "Clicks / month" : "Share of searches"}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.position} className="border-t border-slate-100">
                <td className="py-2 font-semibold tabular-nums text-slate-400">{r.position}</td>
                <td className="max-w-0 py-2 pr-3">
                  {r.domain ? (
                    <a
                      href={`https://${r.domain}`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex max-w-full items-center gap-1 truncate font-medium text-slate-800 hover:text-indigo-600"
                    >
                      <span className="truncate">{r.domain}</span>
                      <ExternalLink size={12} className="shrink-0 text-slate-300" />
                    </a>
                  ) : (
                    <span className="text-slate-400">Position {r.position}</span>
                  )}
                </td>
                <td className="py-2">
                  <div className="flex items-center justify-end gap-2">
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full rounded-full bg-indigo-500" style={{ width: `${(value(r) / max) * 100}%` }} />
                    </div>
                    <span className="w-24 text-right tabular-nums text-slate-700">
                      {known
                        ? `${formatNumber(r.clicks ?? 0)}${r.clicks_low != null && r.clicks_low !== r.clicks_high ? "*" : ""}`
                        : `${(r.ctr ?? 0).toFixed(1)}%`}
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {known && rows.some((r) => r.clicks_low != null && r.clicks_low !== r.clicks_high) && (
        <p className="mt-3 text-xs text-slate-400">* Middle of a range, because several features overlap at this position.</p>
      )}
    </section>
  );
}
