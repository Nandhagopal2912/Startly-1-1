"use client";

import { 
  TrendingUp,
  BarChart2,
  AlertTriangle,
  Layout,
  DollarSign,
  Target
} from "lucide-react";
import { cn } from "../lib/utils";

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
};

export type ReportSection = { title: string; body: string };

export type FullReport = {
  summary: ReportSummary;
  sections: ReportSection[];
};

export function InsightsPanel({ sections }: { sections: ReportSection[] }) {
  const getIcon = (title: string) => {
    const t = title.toLowerCase();
    if (t.includes('market') || t.includes('demand')) return <TrendingUp size={18} />;
    if (t.includes('serp') || t.includes('layout')) return <Layout size={18} />;
    if (t.includes('risk')) return <AlertTriangle size={18} />;
    if (t.includes('commercial') || t.includes('intent')) return <DollarSign size={18} />;
    if (t.includes('scalability') || t.includes('verdict')) return <BarChart2 size={18} />;
    return <Target size={18} />;
  };

  const getStyleClasses = (title: string) => {
    const t = title.toLowerCase();
    if (t.includes('risk')) return {
      card: "bg-rose-50/50 border-rose-100",
      icon: "bg-rose-100 text-rose-600"
    };
    if (t.includes('commercial')) return {
      card: "bg-emerald-50/50 border-emerald-100",
      icon: "bg-emerald-100 text-emerald-600"
    };
    if (t.includes('demand')) return {
      card: "bg-blue-50/50 border-blue-100",
      icon: "bg-blue-100 text-blue-600"
    };
    if (t.includes('scalability')) return {
      card: "bg-amber-50/50 border-amber-100",
      icon: "bg-amber-100 text-amber-600"
    };
    return {
      card: "bg-indigo-50/50 border-indigo-100",
      icon: "bg-indigo-100 text-indigo-600"
    };
  };

  return (
    <div className="space-y-4">
      {sections.map((section, i) => {
        const styles = getStyleClasses(section.title);
        const icon = getIcon(section.title);
        
        return (
          <div 
            key={i}
            className={cn(
              "p-5 rounded-3xl border transition-all hover:shadow-lg hover:scale-[1.01] group",
              styles.card
            )}
          >
            <div className="flex items-center gap-3 mb-2">
              <div className={cn(
                "h-8 w-8 rounded-xl flex items-center justify-center transition-transform group-hover:rotate-6",
                styles.icon
              )}>
                {icon}
              </div>
              <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-800">{section.title}</h4>
            </div>
            <p className="text-sm text-slate-600 leading-relaxed pl-11 font-medium">
              {section.body}
            </p>
          </div>
        );
      })}
    </div>
  );
}
