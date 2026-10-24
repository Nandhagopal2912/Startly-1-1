"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Info, RefreshCw } from "lucide-react";
import { API_BASE, ESTIMATE_NOTE, PROVIDER_NOTES, type ProviderName } from "../lib/analysis";
import { cn } from "../lib/utils";

type ProviderCredits = {
  provider: ProviderName;
  label: string;
  active: boolean;
  configured: boolean;
  dashboard: string;
  used_today: number;
  credits_left: number | null;
  credits_per_month: number | null;
  plan: string | null;
  error: string | null;
};

type CreditsResponse = { demo: boolean; providers: ProviderCredits[]; daily_cap?: number; calls_today?: number };

// The balances, or null when the backend can't be reached.
async function fetchCredits(refresh: boolean): Promise<CreditsResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/credits${refresh ? "?refresh=true" : ""}`);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

/**
 * The owner's data sources: credits left on each server key, a switch for which one this browser analyzes
 * with, Startly's daily cap, and what the chosen source can and can't see.
 */
export function CreditsStatus({
  refreshSignal,
  selected,
  onSelect,
}: {
  refreshSignal: number;
  selected: ProviderName | null;
  onSelect: (provider: ProviderName | null) => void;
}) {
  const [data, setData] = useState<CreditsResponse | null>(null);
  const [offline, setOffline] = useState(false);
  const [loading, setLoading] = useState(false);

  function apply(result: CreditsResponse | null) {
    if (result) setData(result);
    setOffline(!result);
  }

  // Reload after each analysis (the parent bumps refreshSignal); the backend caches provider answers for a minute.
  useEffect(() => {
    let current = true;
    fetchCredits(false).then((result) => current && apply(result));
    return () => {
      current = false;
    };
  }, [refreshSignal]);

  async function refresh() {
    setLoading(true);
    apply(await fetchCredits(true));
    setLoading(false);
  }

  if (offline) {
    return (
      <span>
        <span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-rose-500" />
        Backend offline
      </span>
    );
  }
  if (!data || data.demo) return null;

  const serverDefault = data.providers.find((p) => p.active)?.provider ?? "serpapi";
  const usable = data.providers.filter((p) => p.configured);
  // A saved choice whose key has since been removed falls back to the server default.
  const current = selected && usable.some((p) => p.provider === selected) ? selected : serverDefault;
  const note = PROVIDER_NOTES[current];

  return (
    <>
      <label className="inline-flex items-center gap-1.5">
        Data source
        <select
          value={current}
          onChange={(e) => {
            const value = e.target.value as ProviderName;
            onSelect(value === serverDefault ? null : value);
          }}
          className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-xs font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          aria-label="Search data source for new analyses"
        >
          {data.providers.map((p) => (
            <option key={p.provider} value={p.provider} disabled={!p.configured}>
              {p.label}
              {p.provider === serverDefault ? " (default)" : ""}
              {!p.configured ? " (no key)" : ""}
            </option>
          ))}
        </select>
      </label>

      <span className="inline-flex flex-wrap items-center gap-x-4 gap-y-1">
        {data.providers.map((p) => (
          <a
            key={p.provider}
            href={p.dashboard}
            target="_blank"
            rel="noreferrer"
            className={cn("inline-flex items-center gap-1.5 hover:text-indigo-600", p.provider === current ? "font-semibold text-slate-700" : "")}
            title={
              !p.configured
                ? `No ${p.label} key in backend/.env`
                : p.error ?? `${p.plan ? `${p.plan}. ` : ""}${p.used_today} used today by Startly. Opens your ${p.label} dashboard.`
            }
          >
            <span className={cn("inline-block h-2 w-2 rounded-full", !p.configured ? "bg-slate-300" : p.error ? "bg-amber-500" : "bg-emerald-500")} />
            {`${p.label}: `}
            {!p.configured
              ? "no key"
              : p.credits_left == null
                ? "balance unavailable"
                : `${p.credits_left.toLocaleString()}${p.credits_per_month ? ` of ${p.credits_per_month.toLocaleString()}` : ""} left`}
          </a>
        ))}
        {data.daily_cap != null && (
          <span title="Startly's own safety limit on paid searches per day (MAX_API_CALLS_PER_DAY in backend/.env)">
            Today: {data.calls_today ?? 0} of {data.daily_cap} searches
          </span>
        )}
        <button
          type="button"
          onClick={refresh}
          disabled={loading}
          className="rounded p-0.5 text-slate-400 hover:text-indigo-600 disabled:opacity-50"
          aria-label="Refresh credit balances"
          title="Check the balances again"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
        </button>
      </span>

      <p className={cn("flex w-full items-start gap-1.5 pb-0.5 text-[11px] leading-snug", note.tone === "warn" ? "text-amber-700" : "text-slate-500")}>
        {note.tone === "warn" ? <AlertTriangle size={12} className="mt-0.5 shrink-0" /> : <Info size={12} className="mt-0.5 shrink-0" />}
        <span>
          {note.text} {ESTIMATE_NOTE}
        </span>
      </p>
    </>
  );
}
