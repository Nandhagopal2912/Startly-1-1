"use client";

import { useMemo, useState } from "react";
import { AlertCircle, ArrowLeft, CheckCircle2, ListOrdered, Loader2, X } from "lucide-react";
import { cn, formatNumber } from "../lib/utils";
import { type AnalysisRow, clickTier, clicksValue, hasVolume, postJson, volumeLabel } from "../lib/analysis";
import { KEY_HEADER, type LocalAnalysis, keyTransportIsSecure, latestLocal, previousCheck, previousLocal, updateLocal } from "../lib/ownKey";

const MAX_KEYWORDS = 50;

type ParsedKeyword = { keyword: string; search_volume: number | null };

type Preview = {
  total: number;
  cached: number;
  new_calls: number;
  without_volume: number;
  duplicates_removed: number;
  calls_today?: number;
  daily_cap?: number;
  remaining_calls?: number;
  fits_in_cap: boolean;
  own_key?: boolean;
  demo?: boolean;
  unavailable?: number;
  items?: { keyword: string; cached: boolean; has_volume: boolean }[];
};

type BulkResult = {
  keyword: string;
  status: "ok" | "error";
  rank: number | null;
  analysis?: AnalysisRow;
  error?: string;
  error_code?: number;
};

type BulkResponse = {
  results: BulkResult[];
  analyzed: number;
  errors: number;
  cap_reached: boolean;
  api_calls_used: number;
  own_key_searches?: number;
};

// One keyword per line, optionally followed by a volume: "best crm, 5,000" or "best crm<TAB>5000".
export function parseKeywordList(text: string): ParsedKeyword[] {
  const out: ParsedKeyword[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    if (/^keywords?\b.*\bvolume\b/i.test(line)) continue; // spreadsheet header row
    const m = line.match(/^(.*?)\s*[\t,;]\s*(\d[\d,.\s]*)$/);
    if (m && m[1].trim()) {
      const volume = Number(m[2].replace(/[,\s]/g, ""));
      out.push({ keyword: m[1].trim(), search_volume: Number.isFinite(volume) ? volume : null });
    } else {
      out.push({ keyword: line, search_volume: null });
    }
  }
  return out;
}

function plural(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`;
}

// Same order as the backend: known clicks (most first), then unknown volume by organic CTR, then errors.
function rankResults(results: BulkResult[]): BulkResult[] {
  const key = (r: BulkResult): [number, number] => {
    if (r.status !== "ok" || !r.analysis) return [2, 0];
    if (r.analysis.capturable_clicks != null && hasVolume(r.analysis)) return [0, -r.analysis.capturable_clicks];
    return [1, -(r.analysis.report?.summary.organic_ctr_total ?? 0)];
  };
  const sorted = [...results].sort((a, b) => key(a)[0] - key(b)[0] || key(a)[1] - key(b)[1]);
  let rank = 0;
  return sorted.map((r) => ({ ...r, rank: r.status === "ok" ? ++rank : null }));
}

// Later lines' volumes win, like the backend's de-duplication.
function dedupe(list: ParsedKeyword[]): { items: ParsedKeyword[]; duplicates: number } {
  const byKey = new Map<string, ParsedKeyword>();
  for (const item of list) {
    const k = item.keyword.toLowerCase();
    const prev = byKey.get(k);
    byKey.set(k, prev ? { keyword: prev.keyword, search_volume: item.search_volume ?? prev.search_volume } : item);
  }
  return { items: [...byKey.values()], duplicates: list.length - byKey.size };
}

export function BulkAnalysis({
  mockMode,
  location,
  ownKey = null,
  onClose,
  onResults,
  onOpenKeyword,
}: {
  mockMode: boolean;
  location: string;
  // Public demo with the visitor's own SerpApi key: searches run on that key and results stay in the browser.
  ownKey?: string | null;
  onClose: () => void;
  onResults: (rows: AnalysisRow[]) => void;
  onOpenKeyword: (keyword: string) => void;
}) {
  const [text, setText] = useState("");
  const [step, setStep] = useState<"input" | "preview" | "running" | "results">("input");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [response, setResponse] = useState<BulkResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const parsed = useMemo(() => parseKeywordList(text), [text]);
  const tooMany = parsed.length > MAX_KEYWORDS;
  const body = { keywords: parsed, mock_mode: mockMode, location_name: location, language_name: "English" };

  async function onPreview() {
    setError("");
    if (ownKey) {
      // The browser knows what it already has; only the rest needs searches on the visitor's key.
      const { items, duplicates } = dedupe(parsed);
      const saved = items.filter((i) => latestLocal(i.keyword, location));
      setPreview({
        own_key: true,
        total: items.length,
        cached: saved.length,
        new_calls: items.length - saved.length,
        without_volume: items.filter((i) => i.search_volume == null && !latestLocal(i.keyword, location)?.raw_volume).length,
        duplicates_removed: duplicates,
        fits_in_cap: true,
      });
      setStep("preview");
      return;
    }
    setBusy(true);
    try {
      setPreview(await postJson<Preview>("/bulk/preview", body));
      setStep("preview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function runWithOwnKey(key: string): Promise<BulkResponse> {
    if (!keyTransportIsSecure()) throw new Error("Keys are only sent over HTTPS. Open the site at its https:// address.");
    const { items } = dedupe(parsed);
    const saved: BulkResult[] = [];
    const toSearch: ParsedKeyword[] = [];
    for (const item of items) {
      const local = latestLocal(item.keyword, location);
      if (!local) {
        toSearch.push(item);
      } else if (item.search_volume != null && item.search_volume !== local.raw_volume && local.snapshot && local.snapshot_fetched_at) {
        // New volume for a page the browser already has: re-score it for free.
        const rescored = await postJson<AnalysisRow>("/rescore", {
          keyword: local.keyword,
          location_name: location,
          search_volume: item.search_volume,
          snapshot: local.snapshot,
          snapshot_fetched_at: local.snapshot_fetched_at,
          previous: previousCheck(previousLocal(local)),
        });
        const entry: LocalAnalysis = { ...rescored, local_id: local.local_id };
        updateLocal(entry);
        saved.push({ keyword: item.keyword, status: "ok", rank: null, analysis: entry });
      } else {
        saved.push({ keyword: item.keyword, status: "ok", rank: null, analysis: local });
      }
    }
    const searched = toSearch.length
      ? await postJson<BulkResponse>("/bulk/analyze", { ...body, keywords: toSearch }, { [KEY_HEADER]: key })
      : { results: [], analyzed: 0, errors: 0, cap_reached: false, api_calls_used: 0, own_key_searches: 0 };
    const results = rankResults([...saved, ...searched.results]);
    const errors = results.filter((r) => r.status !== "ok").length;
    return {
      results,
      analyzed: results.length - errors,
      errors,
      cap_reached: false,
      api_calls_used: 0,
      own_key_searches: searched.own_key_searches ?? 0,
    };
  }

  async function onRun() {
    setError("");
    setStep("running");
    try {
      const data = ownKey ? await runWithOwnKey(ownKey) : await postJson<BulkResponse>("/bulk/analyze", body);
      setResponse(data);
      onResults(data.results.flatMap((r) => (r.status === "ok" && r.analysis ? [r.analysis] : [])));
      setStep("results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk analysis failed");
      setStep("preview");
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-slate-900/40 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="w-full max-w-5xl my-8 rounded-[2rem] bg-white shadow-2xl border border-slate-200">
        <div className="flex items-center justify-between px-8 py-6 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <ListOrdered size={20} />
            </div>
            <div>
              <h2 className="text-xl font-black text-slate-900 tracking-tight">Bulk Analysis</h2>
              <p className="text-xs font-medium text-slate-400">Rank up to {MAX_KEYWORDS} keywords by capturable clicks · {location}</p>
            </div>
          </div>
          <button onClick={onClose} aria-label="Close bulk analysis" className="p-2 rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X size={20} />
          </button>
        </div>

        <div className="px-8 py-6">
          {error && (
            <div className="mb-4 flex items-start gap-2 rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
              <AlertCircle size={16} className="mt-0.5 shrink-0" /> {error}
            </div>
          )}

          {step === "input" && (
            <div className="space-y-4">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={12}
                placeholder={"One keyword per line, optionally with monthly volume:\n\nbest crm software, 12000\ncrm for small business, 4400\nfree crm\n\nPasting two columns from a spreadsheet also works."}
                className="w-full rounded-2xl border border-slate-200 bg-slate-50/50 p-4 font-mono text-sm text-slate-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className={cn("text-sm font-semibold", tooMany ? "text-rose-600" : "text-slate-500")}>
                  {parsed.length} keyword{parsed.length === 1 ? "" : "s"}
                  {parsed.length > 0 && ` · ${parsed.filter((p) => p.search_volume != null).length} with volume`}
                  {tooMany && ` · maximum is ${MAX_KEYWORDS}`}
                  {mockMode && " · mock mode (no API calls)"}
                </p>
                <button
                  onClick={onPreview}
                  disabled={!parsed.length || tooMany || busy}
                  className="px-6 py-3 rounded-2xl premium-gradient text-white text-sm font-bold shadow-md disabled:opacity-50"
                >
                  {busy ? "Checking…" : "Check cost"}
                </button>
              </div>
            </div>
          )}

          {step === "preview" && preview && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Stat label="Keywords" value={preview.total} note={preview.duplicates_removed ? `${preview.duplicates_removed} duplicate${preview.duplicates_removed === 1 ? "" : "s"} removed` : undefined} />
                <Stat label={preview.own_key ? "Saved in your browser (free)" : "Cached (free)"} value={preview.cached} />
                <Stat label={preview.own_key ? "Searches on your key" : "New API calls"} value={preview.new_calls} tone={preview.fits_in_cap ? "neutral" : "danger"} />
                {preview.own_key ? (
                  <Stat label="Stored on the server" value={0} note="results stay in this browser" />
                ) : (
                  <Stat label="Left today" value={preview.remaining_calls ?? 0} note={`${preview.calls_today}/${preview.daily_cap} used`} />
                )}
              </div>
              {!preview.fits_in_cap && (
                <p className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
                  This needs {preview.new_calls} API calls but only {preview.remaining_calls} are left today. Keywords past the cap will be skipped. Remove some, or raise MAX_API_CALLS_PER_DAY.
                </p>
              )}
              {preview.demo && (preview.unavailable ?? 0) > 0 && (
                <p className="rounded-2xl border border-indigo-100 bg-indigo-50 px-4 py-3 text-sm font-medium text-indigo-800">
                  {preview.unavailable} keyword{preview.unavailable === 1 ? " isn't" : "s aren't"} in the public demo and will be skipped. Run Startly yourself to analyze any keyword.
                </p>
              )}
              {preview.without_volume > 0 && (
                <p className="text-sm font-medium text-slate-500">
                  {preview.without_volume} keyword{preview.without_volume === 1 ? " has" : "s have"} no volume. They will be ranked by click-through rate after the keywords with clicks.
                </p>
              )}
              <div className="flex flex-wrap justify-between gap-3">
                <button onClick={() => setStep("input")} className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl border border-slate-200 text-sm font-bold text-slate-600 hover:bg-slate-50">
                  <ArrowLeft size={16} /> Edit list
                </button>
                <button onClick={onRun} className="px-6 py-3 rounded-2xl premium-gradient text-white text-sm font-bold shadow-md">
                  {!preview.new_calls
                    ? "Run (free)"
                    : preview.own_key
                      ? `Run (${plural(preview.new_calls, "search", "searches")} on your key)`
                      : `Run (${plural(preview.new_calls, "API call", "API calls")})`}
                </button>
              </div>
            </div>
          )}

          {step === "running" && (
            <div className="py-20 flex flex-col items-center gap-4 text-slate-500">
              <Loader2 size={32} className="animate-spin text-indigo-500" />
              <p className="text-sm font-bold">Analyzing {preview?.total ?? parsed.length} keywords…</p>
              <p className="text-xs font-medium text-slate-400">New keywords take a few seconds each; 4 run at a time.</p>
            </div>
          )}

          {step === "results" && response && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3 text-sm font-semibold text-slate-600">
                <span className="inline-flex items-center gap-1.5 text-emerald-700"><CheckCircle2 size={16} /> {response.analyzed} analyzed</span>
                <span>
                  ·{" "}
                  {ownKey
                    ? `${plural(response.own_key_searches ?? 0, "search", "searches")} on your key`
                    : `${plural(response.api_calls_used, "API call", "API calls")} used`}
                </span>
                {response.errors > 0 && <span className="text-rose-600">· {response.errors} failed{response.cap_reached ? " (daily cap reached)" : ""}</span>}
                <span className="text-slate-400">· Added to the dashboard; export them from there.</span>
              </div>
              <div className="overflow-x-auto rounded-2xl border border-slate-100">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-[11px] font-black uppercase tracking-widest text-slate-400">
                    <tr>
                      <th className="px-4 py-3">#</th>
                      <th className="px-4 py-3">Keyword</th>
                      <th className="px-4 py-3 text-right">Volume</th>
                      <th className="px-4 py-3 text-right">Clicks</th>
                      <th className="px-4 py-3 text-right">#1 worth</th>
                      <th className="px-4 py-3 text-center">Click access</th>
                      <th className="px-4 py-3">Takes clicks</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {response.results.map((r) =>
                      r.status === "ok" && r.analysis ? (
                        <ResultRow key={r.keyword} rank={r.rank} row={r.analysis} onOpen={() => onOpenKeyword(r.analysis!.keyword)} />
                      ) : (
                        <tr key={r.keyword} className="bg-rose-50/30">
                          <td className="px-4 py-3 text-slate-300">—</td>
                          <td className="px-4 py-3 font-bold text-slate-700">{r.keyword}</td>
                          <td colSpan={5} className="px-4 py-3 text-xs font-medium text-rose-600">{r.error}</td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>
              <div className="flex justify-between">
                <button onClick={() => { setText(""); setStep("input"); }} className="px-5 py-3 rounded-2xl border border-slate-200 text-sm font-bold text-slate-600 hover:bg-slate-50">
                  New batch
                </button>
                <button onClick={onClose} className="px-6 py-3 rounded-2xl bg-slate-900 text-white text-sm font-bold">Done</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, note, tone = "neutral" }: { label: string; value: number; note?: string; tone?: "neutral" | "danger" }) {
  return (
    <div className={cn("rounded-2xl border p-4", tone === "danger" ? "border-rose-100 bg-rose-50" : "border-slate-100 bg-slate-50/50")}>
      <div className="text-[10px] font-black uppercase tracking-widest text-slate-400">{label}</div>
      <div className={cn("text-2xl font-black", tone === "danger" ? "text-rose-600" : "text-slate-900")}>{value}</div>
      {note && <div className="text-[11px] font-medium text-slate-400">{note}</div>}
    </div>
  );
}

function ResultRow({ rank, row, onOpen }: { rank: number | null; row: AnalysisRow; onOpen: () => void }) {
  const tier = clickTier(row);
  const first = row.report?.click_model?.positions[0];
  const factors = row.report?.click_model?.factors ?? [];
  const low = row.capturable_clicks_low, high = row.capturable_clicks_high;
  return (
    <tr onClick={onOpen} className="cursor-pointer hover:bg-indigo-50/40" title="Open full analysis">
      <td className="px-4 py-3 font-black text-slate-400 tabular-nums">{rank}</td>
      <td className="px-4 py-3 font-bold text-slate-900">{row.keyword}</td>
      <td className="px-4 py-3 text-right tabular-nums text-slate-600">
        {hasVolume(row) ? formatNumber(row.raw_volume) : "—"}
        <div className="text-[10px] text-slate-400">{volumeLabel(row.volume_source)}</div>
      </td>
      <td className="px-4 py-3 text-right tabular-nums font-black text-slate-900">
        {hasVolume(row) ? clicksValue(row) : `${row.report?.summary.organic_ctr_total?.toFixed(1) ?? "—"}%`}
        {hasVolume(row) && low != null && high != null && low !== high && (
          <div className="text-[10px] font-semibold text-slate-400">{formatNumber(low)}–{formatNumber(high)}</div>
        )}
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-slate-600">
        {first ? (hasVolume(row) && first.clicks != null ? formatNumber(first.clicks) : `${first.ctr.toFixed(1)}%`) : "—"}
      </td>
      <td className="px-4 py-3 text-center">
        <span className={cn("inline-flex px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-wider", tier.className)}>{tier.label}</span>
      </td>
      <td className="px-4 py-3 text-xs font-medium text-slate-500">{factors.map((f) => f.label).join(", ") || "Nothing"}</td>
    </tr>
  );
}
