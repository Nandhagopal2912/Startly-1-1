"use client";

import { FormEvent, useState } from "react";
import { CheckCircle2, ExternalLink, KeyRound, Loader2, ShieldCheck, X } from "lucide-react";
import { postJson } from "../lib/analysis";
import { KEY_HEADER, SERPAPI_SIGNUP_URL, keyIsRemembered, keyTransportIsSecure, readKey } from "../lib/ownKey";

export type KeyInfo = { plan_name: string | null; searches_per_month: number | null; searches_left: number | null };

export function KeyDialog({
  reason,
  localCount,
  onSave,
  onForget,
  onDeleteData,
  onClose,
}: {
  reason?: string;
  localCount: number;
  onSave: (key: string, remember: boolean, info: KeyInfo) => void;
  onForget: () => void;
  onDeleteData: () => void;
  onClose: () => void;
}) {
  const existing = readKey();
  const [key, setKey] = useState(existing ?? "");
  const [remember, setRemember] = useState(existing ? keyIsRemembered() : true);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const secure = keyTransportIsSecure();

  async function submit(e: FormEvent) {
    e.preventDefault();
    const trimmed = key.trim();
    if (!trimmed || !secure) return;
    setError("");
    setChecking(true);
    try {
      // Free: SerpApi's account endpoint doesn't use a search.
      const info = await postJson<KeyInfo & { valid: boolean }>("/key/check", {}, { [KEY_HEADER]: trimmed });
      onSave(trimmed, remember, info);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't check the key");
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="key-dialog-title">
      <div className="my-12 w-full max-w-lg rounded-3xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h2 id="key-dialog-title" className="flex items-center gap-2 text-base font-semibold text-slate-900">
            <KeyRound size={18} className="text-indigo-600" /> Analyze any keyword with your own key
          </h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100" aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4 px-6 py-5">
          {reason && <p className="rounded-2xl bg-indigo-50 px-4 py-3 text-sm text-indigo-900">{reason}</p>}
          {!secure && (
            <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert">
              This page or its API isn&apos;t using HTTPS, so a key typed here could be read in transit. Keys are disabled until the site is
              served over https://.
            </p>
          )}
          <p className="text-sm leading-relaxed text-slate-600">
            The samples are free to explore. To analyze your own keywords, use a SerpApi key: the{" "}
            <a href={SERPAPI_SIGNUP_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-medium text-indigo-600 hover:underline">
              free plan <ExternalLink size={12} />
            </a>{" "}
            includes 250 searches a month. Each new keyword uses one search.
          </p>

          <label className="block">
            <span className="text-xs font-medium text-slate-600">SerpApi key</span>
            <input
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="Paste your key"
              className="mt-1 h-10 w-full rounded-xl border border-slate-300 px-3 font-mono text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-4 w-4 accent-indigo-600" />
            Remember on this device (otherwise it&apos;s forgotten when you close the tab)
          </label>

          {error && <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

          <div className="flex items-start gap-2 rounded-2xl bg-slate-50 px-4 py-3 text-xs leading-relaxed text-slate-600">
            <ShieldCheck size={16} className="mt-0.5 shrink-0 text-emerald-600" />
            <span>
              Your key stays in this browser. It&apos;s sent only with your own searches and is never stored on the server. Your analyses are saved
              in this browser too, so nobody else can see them. Startly is open source, so you can check this yourself.
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <button
              type="submit"
              disabled={checking || !key.trim() || !secure}
              className="inline-flex h-10 items-center gap-2 rounded-xl premium-gradient px-5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {checking ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
              {checking ? "Checking…" : "Check and save"}
            </button>
            {existing && (
              <button type="button" onClick={onForget} className="h-10 rounded-xl border border-slate-200 px-4 text-sm font-medium text-slate-600 hover:bg-slate-50">
                Forget key
              </button>
            )}
          </div>
        </form>

        {localCount > 0 && (
          <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-6 py-4 text-xs text-slate-500">
            <span>{localCount} of your analyses are saved in this browser.</span>
            <button
              type="button"
              onClick={() => {
                if (window.confirm("Delete all analyses saved in this browser? This can't be undone.")) onDeleteData();
              }}
              className="font-medium text-rose-600 hover:underline"
            >
              Delete them
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
