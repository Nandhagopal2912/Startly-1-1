"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { API_BASE } from "../lib/analysis";
import { cn } from "../lib/utils";

type ProviderCredits = {
  provider: string;
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

/** Credits left on the server's SerpApi and Serper keys, plus Startly's own daily safety cap. */
export function CreditsStatus({ refreshSignal }: { refreshSignal: number }) {
  const [data, setData] = useState<CreditsResponse | null>(null);
  const [offline, setOffline] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (refresh: boolean) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/credits${refresh ? "?refresh=true" : ""}`);
      if (!res.ok) throw new Error(String(res.status));
      setData(await res.json());
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  // Reload after each analysis (the parent bumps refreshSignal); the backend caches provider answers for a minute.
  useEffect(() => {
    load(false);
  }, [load, refreshSignal]);

  if (offline) {
    return (
      <span>
        <span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-rose-500" />
        Backend offline
      </span>
    );
  }
  if (!data || data.demo) return null;

  return (
    <span className="inline-flex flex-wrap items-center gap-x-4 gap-y-1">
      {data.providers.map((p) => (
        <a
          key={p.provider}
          href={p.dashboard}
          target="_blank"
          rel="noreferrer"
          className={cn("inline-flex items-center gap-1.5 hover:text-indigo-600", p.active ? "font-semibold text-slate-700" : "")}
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
          {p.active && <span className="rounded bg-indigo-50 px-1 text-[10px] font-semibold text-indigo-700">active</span>}
        </a>
      ))}
      {data.daily_cap != null && (
        <span title="Startly's own safety limit on paid searches per day (MAX_API_CALLS_PER_DAY in backend/.env)">
          Today: {data.calls_today ?? 0} of {data.daily_cap} searches
        </span>
      )}
      <button
        type="button"
        onClick={() => load(true)}
        disabled={loading}
        className="rounded p-0.5 text-slate-400 hover:text-indigo-600 disabled:opacity-50"
        aria-label="Refresh credit balances"
        title="Check the balances again"
      >
        <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
      </button>
    </span>
  );
}
