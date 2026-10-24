"use client";

import { ChevronDown, ExternalLink } from "lucide-react";
import { cn } from "../lib/utils";
import type { AnalysisRow } from "../lib/analysis";

const CONFIDENCE = {
  high: "bg-emerald-50 text-emerald-700",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-rose-50 text-rose-700",
};

export function DetailsPanel({ row }: { row: AnalysisRow }) {
  const report = row.report;
  const model = report?.click_model;
  const breakdown = Object.entries(report?.summary.type_breakdown ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <details className="group rounded-3xl border border-slate-200 bg-white shadow-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-4 [&::-webkit-details-marker]:hidden">
        <span>
          <span className="text-base font-semibold text-slate-900">Details and sources</span>
          <span className="ml-2 text-xs text-slate-500">full write-up, how the estimate was made, everything on the page</span>
        </span>
        <ChevronDown size={18} className="text-slate-400 transition-transform group-open:rotate-180" />
      </summary>

      <div className="grid gap-8 border-t border-slate-100 px-6 py-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Analysis</h4>
          <dl className="mt-3 space-y-4">
            {(report?.sections ?? []).map((s) => (
              <div key={s.title}>
                <dt className="text-sm font-semibold text-slate-800">{s.title}</dt>
                <dd className="mt-0.5 text-sm leading-relaxed text-slate-600">{s.body}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="space-y-8">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Everything on page one</h4>
            <table className="mt-3 w-full text-sm">
              <tbody>
                {breakdown.map(([type, count]) => (
                  <tr key={type} className="border-t border-slate-100 first:border-0">
                    <td className="py-1.5 capitalize text-slate-700">{type.replace(/_/g, " ")}</td>
                    <td className="py-1.5 text-right tabular-nums text-slate-900">{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-slate-500">
              {row.organic_results} of {row.total_results} items are organic links ({(row.saturation_score * 100).toFixed(0)}%).
            </p>
          </div>

          {model && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">How clicks were estimated</h4>
              <ul className="mt-3 space-y-2 text-sm">
                {model.factors.map((f) => (
                  <li key={f.feature} className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-800">{f.label}</span>
                    <span className="tabular-nums text-rose-600">{f.position_1_effect_percent}% at #1</span>
                    <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", CONFIDENCE[f.confidence])}>{f.confidence}</span>
                    <a href={f.url} target="_blank" rel="noreferrer" title={f.source} className="inline-flex items-center gap-0.5 text-xs text-slate-400 hover:text-indigo-600">
                      source <ExternalLink size={11} />
                    </a>
                  </li>
                ))}
                {!model.factors.length && <li className="text-slate-500">No features that reduce organic clicks.</li>}
              </ul>
              <p className="mt-3 text-xs text-slate-500">
                Baseline click rates:{" "}
                <a href={model.baseline_source.url} target="_blank" rel="noreferrer" className="underline hover:text-indigo-600">
                  {model.baseline_source.name}
                </a>
                .{" "}
                <a
                  href="https://github.com/Nandhagopal2912/Startly-1-1/blob/main/METHODOLOGY.md"
                  target="_blank"
                  rel="noreferrer"
                  className="underline hover:text-indigo-600"
                >
                  Full methodology
                </a>
              </p>
            </div>
          )}
        </div>
      </div>
    </details>
  );
}
