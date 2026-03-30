"use client";

import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip
} from "chart.js";
import { Bar, Doughnut } from "react-chartjs-2";

ChartJS.register(ArcElement, CategoryScale, LinearScale, BarElement, Tooltip, Legend);

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
};

export type ReportSection = { title: string; body: string };

export type FullReport = {
  summary: ReportSummary;
  sections: ReportSection[];
};

type Props = {
  keyword: string;
  source: string;
  mock_mode: boolean;
  report: FullReport;
};

const COLORS = [
  "rgba(59, 130, 246, 0.85)",
  "rgba(16, 185, 129, 0.85)",
  "rgba(245, 158, 11, 0.85)",
  "rgba(239, 68, 68, 0.85)",
  "rgba(139, 92, 246, 0.85)",
  "rgba(236, 72, 153, 0.85)"
];

export function AnalyzeReportPanel({ keyword, source, mock_mode, report }: Props) {
  const { summary, sections } = report;
  const types = Object.keys(summary.type_breakdown);
  const doughnutData = {
    labels: types,
    datasets: [
      {
        data: types.map((t) => summary.type_breakdown[t]),
        backgroundColor: types.map((_, i) => COLORS[i % COLORS.length]),
        borderWidth: 1
      }
    ]
  };

  const volumeBar = {
    labels: ["Monthly volumes"],
    datasets: [
      {
        label: "Raw volume",
        data: [summary.raw_volume],
        backgroundColor: "rgba(59, 130, 246, 0.7)"
      },
      {
        label: "Adjusted (true demand)",
        data: [summary.adjusted_volume],
        backgroundColor: "rgba(16, 185, 129, 0.75)"
      }
    ]
  };

  const saturationDoughnut = {
    labels: ["Organic", "Other"],
    datasets: [
      {
        data:
          summary.total_results > 0
            ? [summary.organic_results, summary.non_organic_count]
            : [0, 0],
        backgroundColor: ["rgba(16, 185, 129, 0.85)", "rgba(148, 163, 184, 0.85)"],
        borderWidth: 1
      }
    ]
  };

  return (
    <section className="mb-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-lg">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 pb-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Analyze report
          </p>
          <h2 className="text-2xl font-bold text-slate-900">{keyword}</h2>
          <p className="mt-1 text-sm text-slate-600">
            Source: <span className="font-medium">{source}</span>
            {mock_mode ? " · Mock data (no API charge)" : " · Live DataForSEO"}
          </p>
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2 text-right text-xs text-slate-600">
          <div>Saturation label</div>
          <div className="font-semibold text-slate-800">{summary.saturation_label}</div>
        </div>
      </div>

      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          label="Raw monthly volume"
          value={formatNum(summary.raw_volume)}
          hint="From keyword_data.search_volume"
        />
        <Kpi
          label="Adjusted volume"
          value={formatNum(summary.adjusted_volume)}
          hint={
            summary.penalty_applied
              ? `−${summary.penalty_percent}% penalty (non-organic SERP items)`
              : "No penalty applied"
          }
        />
        <Kpi
          label="Saturation score"
          value={`${(summary.saturation_score * 100).toFixed(1)}%`}
          hint={`${summary.organic_results} organic ÷ ${summary.total_results} total items`}
        />
        <Kpi
          label="Demand / organic slot"
          value={
            summary.demand_per_organic_slot != null
              ? formatNum(summary.demand_per_organic_slot)
              : "—"
          }
          hint="Adjusted volume ÷ organic count"
        />
      </div>

      <div className="mb-8 grid gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-800">Raw vs adjusted demand</h3>
          <div className="h-56">
            <Bar
              data={volumeBar}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } },
                scales: {
                  x: { stacked: false },
                  y: { beginAtZero: true }
                }
              }}
            />
          </div>
          {summary.penalty_applied && (
            <p className="mt-2 text-xs text-slate-600">
              Volume reduction: <strong>{formatNum(summary.volume_reduction)}</strong> (
              {summary.penalty_factor}× multiplier after penalty)
            </p>
          )}
        </div>
        <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-800">Organic vs non-organic (items)</h3>
          <div className="mx-auto h-56 max-w-[240px]">
            <Doughnut
              data={saturationDoughnut}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom" } }
              }}
            />
          </div>
          <ul className="mt-2 space-y-1 text-xs text-slate-600">
            <li>
              Organic: <strong>{summary.organic_results}</strong>
            </li>
            <li>
              Non-organic: <strong>{summary.non_organic_count}</strong>
            </li>
            {summary.non_organic_types.length > 0 && (
              <li>
                Types: {summary.non_organic_types.join(", ")}
              </li>
            )}
          </ul>
        </div>
        <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-800">SERP types (full breakdown)</h3>
          <div className="mx-auto h-56 max-w-[260px]">
            <Doughnut
              data={doughnutData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "right" } }
              }}
            />
          </div>
        </div>
      </div>

      <div className="space-y-6">
        <h3 className="text-lg font-semibold text-slate-900">Detailed explanation</h3>
        {sections.map((sec) => (
          <article key={sec.title} className="rounded-lg border border-slate-100 bg-slate-50/50 p-4">
            <h4 className="mb-2 font-semibold text-slate-800">{sec.title}</h4>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{sec.body}</p>
          </article>
        ))}
      </div>

      <div className="mt-6 rounded-lg border border-blue-100 bg-blue-50/80 p-4 text-sm text-slate-800">
        <strong className="text-blue-900">Quick numbers</strong>
        <ul className="mt-2 grid gap-2 sm:grid-cols-2">
          <li>
            Penalty:{" "}
            <strong>
              {summary.penalty_applied ? `${summary.penalty_percent}%` : "0%"}
            </strong>{" "}
            · Factor: <strong>{summary.penalty_factor}</strong>
          </li>
          <li>
            Saturation: <strong>{summary.saturation_percent}%</strong> organic share of items
          </li>
          <li>
            Total SERP items in response: <strong>{summary.total_results}</strong>
          </li>
          <li>
            Adjusted ÷ organic slots:{" "}
            <strong>
              {summary.demand_per_organic_slot != null
                ? formatNum(summary.demand_per_organic_slot)
                : "N/A"}
            </strong>
          </li>
        </ul>
      </div>
    </section>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums text-slate-900">{value}</div>
      <div className="mt-2 text-xs text-slate-600">{hint}</div>
    </div>
  );
}

function formatNum(n: number): string {
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}
