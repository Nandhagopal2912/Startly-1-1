import type { FullReport } from "../components/AnalyzeReport";
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
export function clickTier(row: AnalysisRow) {
  const loss = row.report?.summary.penalty_percent ?? 0;
  if (loss < 25) return { label: "Open", className: "bg-emerald-100 text-emerald-700 border border-emerald-200" };
  if (loss < 50) return { label: "Contested", className: "bg-amber-100 text-amber-700 border border-amber-200" };
  return { label: "Click-hostile", className: "bg-rose-100 text-rose-700 border border-rose-200" };
}
