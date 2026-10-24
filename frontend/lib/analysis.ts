import type { FullReport, SerpChanges } from "../components/AnalyzeReport";
import { formatNumber } from "./utils";

export type AnalysisRow = {
  keyword: string;
  raw_volume: number;
  adjusted_volume: number;
  saturation_score: number;
  organic_results: number;
  total_results: number;
  penalty_applied: boolean;
  source: string;
  mock_mode: boolean;
  provider?: string;
  volume_source?: string;
  capturable_clicks?: number | null;
  capturable_clicks_low?: number | null;
  capturable_clicks_high?: number | null;
  analysis_id?: number;
  analyzed_at?: string;
  rescored?: boolean;
  changes?: SerpChanges;
  location_name?: string;
  language_name?: string;
  demo?: boolean;
  // Analyses made with the visitor's own SerpApi key (kept in their browser, see lib/ownKey.ts).
  own_key?: boolean;
  snapshot?: { keyword: string; provider: string; items: { type: string; rank_group: number | null; domain: string | null }[] };
  snapshot_fetched_at?: string;
  local_id?: string;
  report?: FullReport;
};

const VOLUME_LABELS: Record<string, string> = {
  user: "Your entry",
  dataforseo: "DataForSEO",
  mock: "Mock data",
  api: "API",
  unknown: "No volume",
};

export function volumeLabel(source?: string) {
  return VOLUME_LABELS[source ?? "unknown"] ?? source ?? "No volume";
}

export function hasVolume(row: AnalysisRow) {
  return row.volume_source !== "unknown";
}

export function clicksValue(row: AnalysisRow) {
  return hasVolume(row) && row.capturable_clicks != null ? formatNumber(row.capturable_clicks) : "—";
}

export function clicksDescription(row: AnalysisRow) {
  const { capturable_clicks_low: low, capturable_clicks_high: high } = row;
  if (!hasVolume(row) || row.capturable_clicks == null) {
    const ctr = row.report?.summary.organic_ctr_total;
    return ctr != null ? `${ctr.toFixed(1)}% of searches click organic` : "Enter a volume to estimate clicks";
  }
  if (low != null && high != null && low !== high) return `Range ${formatNumber(low)}–${formatNumber(high)} a month`;
  return "Monthly organic clicks on page one";
}

// Tier by how many clicks SERP features take, compared with a plain results page.
export function tierForLoss(loss: number) {
  if (loss < 25) return { label: "Open", className: "bg-emerald-100 text-emerald-700 border border-emerald-200" };
  if (loss < 50) return { label: "Contested", className: "bg-amber-100 text-amber-700 border border-amber-200" };
  return { label: "Click-hostile", className: "bg-rose-100 text-rose-700 border border-rose-200" };
}

export function clickTier(row: AnalysisRow) {
  return tierForLoss(row.report?.summary.penalty_percent ?? 0);
}

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

// Countries the SERP providers can target (see COUNTRY_CODES in backend/providers/serper.py).
export const COUNTRIES = [
  "United States", "United Kingdom", "India", "Canada", "Australia", "Germany", "France", "Spain", "Italy",
  "Netherlands", "Brazil", "Mexico", "Japan", "Singapore", "United Arab Emirates", "South Africa",
  "New Zealand", "Ireland",
];

export const DEFAULT_COUNTRY = "United States";

export function rowCountry(row: AnalysisRow) {
  return row.location_name ?? DEFAULT_COUNTRY;
}

export type SortKey = "clicks" | "volume" | "recent" | "name";

export function sortRows(rows: AnalysisRow[], key: SortKey): AnalysisRow[] {
  const clicks = (r: AnalysisRow) => (hasVolume(r) ? r.capturable_clicks ?? -1 : -1);
  const sorted = [...rows];
  if (key === "clicks") sorted.sort((a, b) => clicks(b) - clicks(a) || a.keyword.localeCompare(b.keyword));
  if (key === "volume") sorted.sort((a, b) => (hasVolume(b) ? b.raw_volume : -1) - (hasVolume(a) ? a.raw_volume : -1));
  if (key === "recent") sorted.sort((a, b) => (b.analysis_id ?? 0) - (a.analysis_id ?? 0));
  if (key === "name") sorted.sort((a, b) => a.keyword.localeCompare(b.keyword));
  return sorted;
}

// POST JSON and return the parsed body, turning FastAPI's {"detail": ...} errors into readable messages.
export async function postJson<T>(path: string, body: unknown, headers: Record<string, string> = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
    });
  } catch {
    // The browser hides the reason: usually the backend is down, or it doesn't allow this page's address (CORS).
    throw new Error(
      `Can't reach the backend at ${API_BASE}. Check that it's running, and that this page's address ` +
        `(${window.location.origin}) is allowed in ALLOWED_ORIGINS.`
    );
  }
  const text = await res.text();
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = JSON.parse(text);
      if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* keep the generic message */
    }
    throw new Error(detail);
  }
  return JSON.parse(text) as T;
}

// Per-browser marker: analyses up to this id were cleared from the dashboard (history keeps them).
const CLEARED_KEY = "startly.dashboardClearedAfterId";

export function readClearedAfterId(): number {
  try {
    return Number(window.localStorage.getItem(CLEARED_KEY)) || 0;
  } catch {
    return 0;
  }
}

// Per-browser: keywords removed from the dashboard -> the analysis id they were removed at.
// A newer analysis of the same keyword brings it back.
const HIDDEN_KEY = "startly.dashboardHidden";

export function readHidden(): Record<string, number> {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(HIDDEN_KEY) ?? "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function hideKeyword(keyword: string, analysisId: number) {
  try {
    const hidden = readHidden();
    hidden[keyword.toLowerCase()] = Math.max(hidden[keyword.toLowerCase()] ?? 0, analysisId);
    window.localStorage.setItem(HIDDEN_KEY, JSON.stringify(hidden));
  } catch {
    /* storage unavailable: removal just won't survive a refresh */
  }
}

export function isHidden(row: AnalysisRow, hidden: Record<string, number>) {
  const at = hidden[row.keyword.toLowerCase()];
  return at !== undefined && (row.analysis_id ?? 0) <= at;
}

export function writeClearedAfterId(id: number) {
  try {
    window.localStorage.setItem(CLEARED_KEY, String(id));
  } catch {
    /* storage unavailable: clearing just won't survive a refresh */
  }
}
