// Shapes of the /analyze response's report, shared by the dashboard components.

export type ReportSummary = {
  keyword: string;
  raw_volume: number;
  adjusted_volume: number;
  saturation_score: number;
  saturation_percent: number;
  organic_results: number;
  non_organic_count: number;
  total_results: number;
  penalty_applied: boolean;
  penalty_percent: number;
  penalty_factor: number;
  volume_reduction: number;
  type_breakdown: Record<string, number>;
  non_organic_types: string[];
  demand_per_organic_slot: number | null;
  saturation_label: string;
  saturation_status?: 'success' | 'warning' | 'danger';
  saturation_desc?: string;
  capturable_clicks?: number | null;
  capturable_clicks_low?: number | null;
  capturable_clicks_high?: number | null;
  organic_ctr_total?: number;
};

export type ReportSection = { title: string; body: string };

export type ClickPosition = {
  position: number;
  ctr: number;
  ctr_low: number;
  ctr_high: number;
  clicks: number | null;
  clicks_low: number | null;
  clicks_high: number | null;
};

export type ClickFactor = {
  feature: string;
  label: string;
  position_1_effect_percent: number;
  confidence: "high" | "medium" | "low";
  source: string;
  url: string;
};

export type ClickModel = {
  positions: ClickPosition[];
  factors: ClickFactor[];
  neutral_features: string[];
  low_confidence_factors: string[];
  baseline_source: { name: string; url: string };
};

export type SerpChanges = {
  has_previous: boolean;
  current_fetched_at?: string | null;
  previous_fetched_at?: string;
  has_changes?: boolean;
  summary?: string[];
  features_added?: { type: string; label: string }[];
  features_removed?: { type: string; label: string }[];
  feature_counts_changed?: { type: string; label: string; before: number; after: number }[];
  organic_before?: number;
  organic_after?: number;
  domains_entered?: { domain: string; position: number }[];
  domains_left?: { domain: string; position: number }[];
  domains_moved?: { domain: string; before: number; after: number }[];
  clicks_before?: number | null;
  clicks_after?: number | null;
  ctr_before?: number;
  ctr_after?: number;
  click_loss_before?: number;
  click_loss_after?: number;
};

export type Verdict = {
  label: string;
  tone: "good" | "neutral" | "bad" | "unknown";
  reason: string;
  top1_clicks: number | null;
  top3_clicks: number | null;
};

export type Recommendation = { id: string; tone: "action" | "warning" | "info"; title: string; detail: string };

export type PageOneRow = {
  position: number;
  domain: string | null;
  ctr: number | null;
  clicks: number | null;
  clicks_low: number | null;
  clicks_high: number | null;
};

export type FullReport = {
  summary: ReportSummary;
  sections: ReportSection[];
  click_model?: ClickModel;
  verdict?: Verdict;
  recommendations?: Recommendation[];
  page_one?: PageOneRow[];
};
