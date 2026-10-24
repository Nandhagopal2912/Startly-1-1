"use client";

import { AlertTriangle, ArrowRightCircle, CheckCircle2, Info } from "lucide-react";
import { cn } from "../lib/utils";
import type { Recommendation } from "./AnalyzeReport";

const TONES = {
  action: { icon: <ArrowRightCircle size={18} />, className: "text-indigo-600 bg-indigo-50" },
  warning: { icon: <AlertTriangle size={18} />, className: "text-amber-600 bg-amber-50" },
  info: { icon: <Info size={18} />, className: "text-slate-500 bg-slate-100" },
};

export function Recommendations({ items }: { items?: Recommendation[] }) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <h3 className="text-base font-semibold text-slate-900">What to do</h3>
      <p className="mt-0.5 text-xs text-slate-500">Based on what Google shows for this search</p>
      {items === undefined ? (
        <p className="mt-4 text-sm text-slate-500">Analyze this keyword again to get recommendations.</p>
      ) : items.length === 0 ? (
        <p className="mt-4 inline-flex items-center gap-2 text-sm text-emerald-700">
          <CheckCircle2 size={16} /> A plain results page: nothing special to plan around. Focus on ranking well.
        </p>
      ) : (
        <ol className="mt-4 space-y-4">
          {items.map((item) => (
            <li key={item.id} className="flex gap-3">
              <span className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl", TONES[item.tone].className)}>
                {TONES[item.tone].icon}
              </span>
              <div>
                <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                <p className="mt-0.5 text-sm leading-relaxed text-slate-600">{item.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
