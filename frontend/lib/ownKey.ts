// Everything a visitor does with their own SerpApi key lives in their browser: the key itself and their
// analyses. The server never stores either (see backend/stateless.py).
import { API_BASE, type AnalysisRow } from "./analysis";

const KEY_STORAGE = "startly.serpapiKey";
const ANALYSES_STORAGE = "startly.localAnalyses";
// localStorage holds about 5 MB; an analysis with its results page is roughly 10-20 KB.
const MAX_LOCAL_ANALYSES = 150;

export const KEY_HEADER = "X-SerpApi-Key";
export const SERPAPI_SIGNUP_URL = "https://serpapi.com/users/sign_up";

export type LocalAnalysis = AnalysisRow & { local_id: string; hidden?: boolean };

// --- the key ---

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

/** A key may only travel over HTTPS (or stay on this machine): both this page and the API must be secure. */
export function keyTransportIsSecure(): boolean {
  try {
    const api = new URL(API_BASE);
    const apiSecure = api.protocol === "https:" || LOCAL_HOSTS.has(api.hostname);
    return apiSecure && window.isSecureContext;
  } catch {
    return false;
  }
}


// "Remember on this device" keeps it in localStorage; otherwise sessionStorage (gone when the tab closes).
export function readKey(): string | null {
  try {
    return window.localStorage.getItem(KEY_STORAGE) ?? window.sessionStorage.getItem(KEY_STORAGE);
  } catch {
    return null;
  }
}

export function saveKey(key: string, remember: boolean) {
  try {
    forgetKey();
    (remember ? window.localStorage : window.sessionStorage).setItem(KEY_STORAGE, key);
  } catch {
    /* storage blocked: the key works until the page reloads */
  }
}

export function forgetKey() {
  try {
    window.localStorage.removeItem(KEY_STORAGE);
    window.sessionStorage.removeItem(KEY_STORAGE);
  } catch {
    /* nothing to forget */
  }
}

export function keyIsRemembered(): boolean {
  try {
    return window.localStorage.getItem(KEY_STORAGE) !== null;
  } catch {
    return false;
  }
}

// --- the visitor's analyses ---

export function listLocal(): LocalAnalysis[] {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(ANALYSES_STORAGE) ?? "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeLocal(items: LocalAnalysis[]) {
  let list = items.slice(-MAX_LOCAL_ANALYSES);
  // If storage is full, drop the oldest analyses until it fits.
  while (list.length) {
    try {
      window.localStorage.setItem(ANALYSES_STORAGE, JSON.stringify(list));
      return;
    } catch {
      list = list.slice(Math.ceil(list.length / 4));
    }
  }
}

const sameQuery = (a: AnalysisRow, keyword: string, country: string) =>
  a.keyword.toLowerCase() === keyword.trim().toLowerCase() && (a.location_name ?? "United States") === country;

function newId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/** Save a new analysis (a fresh search or re-check) and return it with its local id. */
export function addLocal(row: AnalysisRow): LocalAnalysis {
  const entry: LocalAnalysis = { ...row, local_id: newId() };
  writeLocal([...listLocal(), entry]);
  return entry;
}

/** Replace an existing analysis in place (e.g. after a volume edit re-scores it). */
export function updateLocal(entry: LocalAnalysis) {
  writeLocal(listLocal().map((e) => (e.local_id === entry.local_id ? entry : e)));
}

export function getLocal(localId: string): LocalAnalysis | undefined {
  return listLocal().find((e) => e.local_id === localId);
}

/** The newest analysis of this keyword in this country, if the visitor has one. */
export function latestLocal(keyword: string, country: string): LocalAnalysis | undefined {
  return listLocal().filter((e) => sameQuery(e, keyword, country)).at(-1);
}

/** The analysis before `entry` for the same keyword: what a re-check compares against. */
export function previousLocal(entry: LocalAnalysis): LocalAnalysis | undefined {
  const list = listLocal().filter((e) => sameQuery(e, entry.keyword, entry.location_name ?? "United States"));
  const i = list.findIndex((e) => e.local_id === entry.local_id);
  return i > 0 ? list[i - 1] : undefined;
}

/** Newest analysis per keyword and country, newest first, skipping ones removed from the dashboard. */
export function dashboardLocal(): LocalAnalysis[] {
  const latest = new Map<string, LocalAnalysis>();
  for (const e of listLocal()) latest.set(`${e.keyword.toLowerCase()}|${e.location_name ?? "United States"}`, e);
  return [...latest.values()].filter((e) => !e.hidden).reverse();
}

/** Remove from the dashboard but keep in this browser's history; a new analysis brings it back. */
export function hideLocal(keyword: string) {
  writeLocal(listLocal().map((e) => (e.keyword.toLowerCase() === keyword.toLowerCase() ? { ...e, hidden: true } : e)));
}

export function hideAllLocal() {
  writeLocal(listLocal().map((e) => ({ ...e, hidden: true })));
}

export function deleteAllLocal() {
  try {
    window.localStorage.removeItem(ANALYSES_STORAGE);
  } catch {
    /* nothing stored */
  }
}

/** The previous check in the shape the backend expects, for comparing a re-check. */
export function previousCheck(entry: AnalysisRow | undefined) {
  return entry?.snapshot && entry.snapshot_fetched_at
    ? { snapshot: entry.snapshot, fetched_at: entry.snapshot_fetched_at }
    : undefined;
}
