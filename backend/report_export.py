"""CSV exports of dashboard analyses: one tidy table per file, safe to open in Excel."""

from __future__ import annotations

import csv
import io
from typing import Any

from report_data import VOLUME_LABELS, clicks, features, has_volume, positions, ranked, report, summary

# Excel and Sheets run cells that start with these as formulas, so a keyword like "=HYPERLINK(...)" could execute.
_FORMULA_PREFIXES = ("=", "+", "-", "@", chr(9), chr(13))  # chr(9) = tab, chr(13) = carriage return


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return int(value)  # 12000, not 12000.0
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _csv(header: list[str], rows: list[list[Any]]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows([[_cell(v) for v in r] for r in rows])
    # The BOM makes Excel read the file as UTF-8 (keywords and dashes stay intact).
    return ("﻿" + out.getvalue()).encode("utf-8")


# --- CSV ---

KEYWORD_COLUMNS = [
    "Rank", "Keyword", "Country", "Verdict", "Capturable clicks / month", "Clicks (low)", "Clicks (high)",
    "#1 ranking clicks / month", "Top 3 clicks / month", "Monthly searches", "Volume source",
    "Clicks lost to SERP features (%)", "Organic click-through (% of searches)", "Organic results on page one",
    "Features that reduce clicks", "Other features on page one", "Top 3 ranking sites", "First recommendation",
    "Analyzed", "Data source", "Notes",
]


def generate_keywords_csv(rows: list[dict[str, Any]]) -> bytes:
    """One row per keyword, ranked like the dashboard."""
    out = []
    for rank, row in enumerate(ranked(rows), start=1):
        rep, s = report(row), summary(row)
        verdict = rep.get("verdict") or {}
        mid, low, high = clicks(row)
        costly, neutral = features(row)
        sites = [p.get("domain") for p in (rep.get("page_one") or [])[:3] if p.get("domain")]
        recs = rep.get("recommendations") or []
        notes = [n for n in (
            "Mock data" if row.get("mock_mode") else "",
            "Recalculated with the current click model" if row.get("rescored") else "",
            "Your own key" if row.get("own_key") else "",
        ) if n]
        out.append([
            rank, row.get("keyword", ""), row.get("location_name") or "United States", verdict.get("label", ""),
            mid, low, high, verdict.get("top1_clicks"), verdict.get("top3_clicks"),
            row.get("raw_volume") if has_volume(row) else None,
            VOLUME_LABELS.get(row.get("volume_source") or "unknown", row.get("volume_source")),
            s.get("penalty_percent"), s.get("organic_ctr_total"), row.get("organic_results", s.get("organic_results")),
            "; ".join(costly), "; ".join(neutral), "; ".join(sites), recs[0]["title"] if recs else "",
            (row.get("analyzed_at") or "")[:10], row.get("provider", ""), "; ".join(notes),
        ])
    return _csv(KEYWORD_COLUMNS, out)


RANKING_COLUMNS = [
    "Keyword", "Country", "Position", "Site", "Clicks / month", "Clicks (low)", "Clicks (high)",
    "Share of searches (%)", "Analyzed",
]


def generate_rankings_csv(rows: list[dict[str, Any]]) -> bytes:
    """One row per keyword and organic position: who ranks and what that position is worth."""
    out = []
    for row in ranked(rows):
        known = has_volume(row)
        for p in positions(row):
            out.append([
                row.get("keyword", ""), row.get("location_name") or "United States", p.get("position"), p.get("domain") or "",
                p.get("clicks") if known else None, p.get("clicks_low") if known else None,
                p.get("clicks_high") if known else None, p.get("ctr"), (row.get("analyzed_at") or "")[:10],
            ])
    return _csv(RANKING_COLUMNS, out)
