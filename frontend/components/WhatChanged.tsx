"use client";

import { ArrowDownRight, ArrowUpRight, CheckCircle2, GitCompare, Loader2, Minus, Plus, RefreshCw } from "lucide-react";
import { cn, formatNumber } from "../lib/utils";
import type { SerpChanges } from "./AnalyzeReport";

function formatDate(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function WhatChanged({
  changes,
  rechecking,
  costNote,
  onRecheck,
}: {
  changes?: SerpChanges;
  rechecking: boolean;
  costNote: string;
  onRecheck?: () => void; // omitted when re-checking isn't allowed (public demo)
}) {
  const hasPrevious = changes?.has_previous;
  const clicksMoved =
    changes?.clicks_before != null && changes?.clicks_after != null && changes.clicks_before !== changes.clicks_after;

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="flex items-center gap-2 text-base font-semibold text-slate-900">
            <GitCompare size={18} className="text-indigo-500" /> What changed
          </h3>
          <p className="mt-0.5 text-xs text-slate-500">
            {hasPrevious
              ? `Page checked ${formatDate(changes?.current_fetched_at)}, compared with ${formatDate(changes?.previous_fetched_at)}`
              : changes?.current_fetched_at
                ? `Page checked ${formatDate(changes.current_fetched_at)}`
                : "Re-check to fetch the page again and compare"}
          </p>
        </div>
        {onRecheck && (
        <button
          type="button"
          onClick={onRecheck}
          disabled={rechecking}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600 disabled:opacity-50"
          title={costNote}
        >
          {rechecking ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          {rechecking ? "Re-checking…" : "Re-check now"}
        </button>
        )}
      </div>

      {!hasPrevious && (
        <p className="text-sm font-medium text-slate-500">
          This is the first saved check of this keyword.{" "}
          {onRecheck ? <>Re-check later to see how Google&apos;s page changes. {costNote}</> : costNote}
        </p>
      )}

      {hasPrevious && !changes?.has_changes && (
        <p className="inline-flex items-center gap-2 rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
          <CheckCircle2 size={16} /> No changes since the previous check.
        </p>
      )}

      {hasPrevious && changes?.has_changes && (
        <div className="space-y-6">
          {clicksMoved && (
            <div
              className={cn(
                "inline-flex items-center gap-2 rounded-2xl border px-4 py-3 text-sm font-black",
                changes.clicks_after! < changes.clicks_before! ? "border-rose-100 bg-rose-50 text-rose-700" : "border-emerald-100 bg-emerald-50 text-emerald-700"
              )}
            >
              {changes.clicks_after! < changes.clicks_before! ? <ArrowDownRight size={16} /> : <ArrowUpRight size={16} />}
              Capturable clicks {formatNumber(changes.clicks_before!)} → {formatNumber(changes.clicks_after!)}
              <span className="font-semibold opacity-70">
                (click loss {changes.click_loss_before}% → {changes.click_loss_after}%)
              </span>
            </div>
          )}

          <div className="grid gap-6 md:grid-cols-2">
            <ChangeList
              title="SERP features"
              empty="Same features as before"
              items={[
                ...(changes.features_added ?? []).map((f) => ({ icon: "plus" as const, text: `${f.label} appeared` })),
                ...(changes.features_removed ?? []).map((f) => ({ icon: "minus" as const, text: `${f.label} disappeared` })),
                ...(changes.feature_counts_changed ?? []).map((f) => ({
                  icon: f.after > f.before ? ("plus" as const) : ("minus" as const),
                  text: `${f.label}: ${f.before} → ${f.after}`,
                })),
                ...(changes.organic_before !== changes.organic_after
                  ? [{ icon: "neutral" as const, text: `Organic results: ${changes.organic_before} → ${changes.organic_after}` }]
                  : []),
              ]}
            />
            <ChangeList
              title="Organic rankings"
              empty="Same sites in the same order"
              items={[
                ...(changes.domains_moved ?? []).map((m) => ({
                  icon: m.after < m.before ? ("up" as const) : ("down" as const),
                  text: `${m.domain}: #${m.before} → #${m.after}`,
                })),
                ...(changes.domains_entered ?? []).map((e) => ({ icon: "plus" as const, text: `${e.domain} new at #${e.position}` })),
                ...(changes.domains_left ?? []).map((l) => ({ icon: "minus" as const, text: `${l.domain} dropped (was #${l.position})` })),
              ]}
            />
          </div>
        </div>
      )}
    </section>
  );
}

// Defined at module level (not inside WhatChanged) so the lists aren't remounted on every render.
type ChangeIcon = "plus" | "minus" | "up" | "down" | "neutral";

const CHANGE_ICONS: Record<ChangeIcon, { el: JSX.Element; className: string }> = {
  plus: { el: <Plus size={14} />, className: "text-emerald-600 bg-emerald-50" },
  minus: { el: <Minus size={14} />, className: "text-rose-600 bg-rose-50" },
  up: { el: <ArrowUpRight size={14} />, className: "text-emerald-600 bg-emerald-50" },
  down: { el: <ArrowDownRight size={14} />, className: "text-rose-600 bg-rose-50" },
  neutral: { el: <Minus size={14} />, className: "text-slate-500 bg-slate-100" },
};

function ChangeList({ title, empty, items }: { title: string; empty: string; items: { icon: ChangeIcon; text: string }[] }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h4>
      {items.length ? (
        <ul className="space-y-2">
          {items.map((item, i) => (
            <li key={i} className="flex items-center gap-3 text-sm text-slate-700">
              <span className={cn("h-6 w-6 shrink-0 rounded-lg flex items-center justify-center", CHANGE_ICONS[item.icon].className)}>
                {CHANGE_ICONS[item.icon].el}
              </span>
              {item.text}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm font-medium text-slate-400">{empty}</p>
      )}
    </div>
  );
}
