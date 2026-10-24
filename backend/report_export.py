"""CSV and PDF exports of dashboard analyses.

CSV: one tidy table per file (keywords, or page-one rankings), safe to open in Excel.
PDF: a ranked summary page, then one page per keyword in the same order as the dashboard.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# A4 width minus the 18 mm margins on each side.
CONTENT_WIDTH = 174 * mm

METHODOLOGY_URL = "https://github.com/Nandhagopal2912/Startly-1-1/blob/main/METHODOLOGY.md"

VOLUME_LABELS = {"user": "Entered by user", "dataforseo": "DataForSEO", "mock": "Mock data", "api": "API", "unknown": "Unknown"}
VERDICT_COLORS = {"good": "#047857", "neutral": "#b45309", "bad": "#be123c", "unknown": "#475569"}

# Excel and Sheets run cells that start with these as formulas, so a keyword like "=HYPERLINK(...)" could execute.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


# --- shared helpers ---

def _report(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("report") or {}


def _summary(row: dict[str, Any]) -> dict[str, Any]:
    return _report(row).get("summary") or {}


def _has_volume(row: dict[str, Any]) -> bool:
    return (row.get("volume_source") or "") not in ("unknown", "")


def _clicks(row: dict[str, Any]) -> tuple[Any, Any, Any]:
    s = _summary(row)
    mid = row.get("capturable_clicks", s.get("capturable_clicks"))
    low = row.get("capturable_clicks_low", s.get("capturable_clicks_low"))
    high = row.get("capturable_clicks_high", s.get("capturable_clicks_high"))
    if not _has_volume(row):
        return None, None, None
    return mid, low, high


def _features(row: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(features that reduce clicks, other features present), as readable labels."""
    model = _report(row).get("click_model") or {}
    costly = [f"{f['label']} ({f['position_1_effect_percent']}% at #1)" for f in model.get("factors") or []]
    neutral = [t.replace("_", " ").capitalize() for t in model.get("neutral_features") or []]
    return costly, neutral


def ranked(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dashboard order: most capturable clicks first, then keywords without volume by organic click-through."""
    def key(row):
        mid, _, _ = _clicks(row)
        if mid is not None:
            return (0, -float(mid))
        return (1, -float(_summary(row).get("organic_ctr_total") or 0))
    return sorted(rows, key=key)


def _when(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d %b %Y")
    except ValueError:
        return iso


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
        rep, s = _report(row), _summary(row)
        verdict = rep.get("verdict") or {}
        mid, low, high = _clicks(row)
        costly, neutral = _features(row)
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
            row.get("raw_volume") if _has_volume(row) else None,
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
        rep = _report(row)
        positions = rep.get("page_one") or [
            {**p, "domain": None} for p in (rep.get("click_model") or {}).get("positions") or []
        ]
        known = _has_volume(row)
        for p in positions:
            out.append([
                row.get("keyword", ""), row.get("location_name") or "United States", p.get("position"), p.get("domain") or "",
                p.get("clicks") if known else None, p.get("clicks_low") if known else None,
                p.get("clicks_high") if known else None, p.get("ctr"), (row.get("analyzed_at") or "")[:10],
            ])
    return _csv(RANKING_COLUMNS, out)


# --- PDF ---

def _pdf_text(text: Any) -> str:
    """Escape for ReportLab markup and replace characters the built-in Helvetica can't draw."""
    s = str(text if text is not None else "")
    for bad, good in (("→", "to"), ("≈", "~"), ("−", "-"), ("‑", "-"), (" ", " ")):
        s = s.replace(bad, good)
    return escape(s)


def _num(value: Any, suffix: str = "") -> str:
    if value is None or value == "":
        return "-"
    return f"{float(value):,.0f}{suffix}"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    ink, muted = colors.HexColor("#0f172a"), colors.HexColor("#64748b")
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=20, leading=24, alignment=TA_LEFT, textColor=ink, spaceAfter=2),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=17, leading=21, textColor=ink, spaceAfter=2),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=11.5, leading=14, textColor=ink, spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=9.5, leading=13, textColor=colors.HexColor("#334155")),
        "muted": ParagraphStyle("muted", parent=base["BodyText"], fontSize=8.5, leading=11, textColor=muted),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontSize=7.5, leading=10, textColor=muted),
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontSize=8.5, leading=10.5, textColor=ink),
        "cell_head": ParagraphStyle("cell_head", parent=base["BodyText"], fontSize=7.5, leading=9, textColor=muted),
        "big": ParagraphStyle("big", parent=base["BodyText"], fontSize=16, leading=19, textColor=ink, fontName="Helvetica-Bold"),
    }


_GRID = TableStyle([
    ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#cbd5e1")),
    ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 3.5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
])


def _verdict_markup(verdict: dict[str, Any]) -> str:
    color = VERDICT_COLORS.get(verdict.get("tone", "unknown"), "#475569")
    return f'<font color="{color}"><b>{_pdf_text(verdict.get("label", "-"))}</b></font>'


def _summary_page(rows: list[dict[str, Any]], st: dict[str, ParagraphStyle], generated: str) -> list[Any]:
    countries = sorted({r.get("location_name") or "United States" for r in rows})
    flow: list[Any] = [
        Paragraph("Keyword opportunity report", st["title"]),
        Paragraph(_pdf_text(f"{len(rows)} keyword{'s' if len(rows) != 1 else ''} · {', '.join(countries)} · generated {generated}"), st["muted"]),
        Spacer(1, 6),
        Paragraph(
            "<b>Capturable clicks</b> are the monthly searches expected to click an organic result on page one, after "
            "AI Overviews, ads and maps take their share. Keywords are ranked by them; the range shows uncertainty "
            "where several features overlap.", st["body"]),
        Spacer(1, 10),
    ]
    head = ["#", "Keyword", "Verdict", "Clicks / month", "#1 worth", "Clicks lost", "Searches"]
    data = [[Paragraph(h, st["cell_head"]) for h in head]]
    for i, row in enumerate(rows, start=1):
        verdict = _report(row).get("verdict") or {}
        mid, low, high = _clicks(row)
        clicks = _num(mid) + (f"<br/><font size=7 color='#64748b'>{_num(low)}-{_num(high)}</font>" if mid is not None and low != high else "")
        data.append([
            Paragraph(str(i), st["cell"]),
            Paragraph(f"<b>{_pdf_text(row.get('keyword', ''))}</b>", st["cell"]),
            Paragraph(_verdict_markup(verdict), st["cell"]),
            Paragraph(clicks, st["cell"]),
            Paragraph(_num(verdict.get("top1_clicks")), st["cell"]),
            Paragraph(f"{_summary(row).get('penalty_percent', 0)}%", st["cell"]),
            Paragraph(_num(row.get("raw_volume")) if _has_volume(row) else "-", st["cell"]),
        ])
    table = Table(data, colWidths=[8 * mm, 54 * mm, 34 * mm, 24 * mm, 18 * mm, 18 * mm, 18 * mm], repeatRows=1)
    table.setStyle(_GRID)
    flow.append(table)
    if any(not _has_volume(r) for r in rows):
        flow += [Spacer(1, 6), Paragraph("Keywords without a monthly search volume show click-through only and are listed last.", st["small"])]
    return flow


def _keyword_page(row: dict[str, Any], st: dict[str, ParagraphStyle]) -> list[Any]:
    rep, s = _report(row), _summary(row)
    verdict = rep.get("verdict") or {}
    mid, low, high = _clicks(row)
    meta = [row.get("location_name") or "United States"]
    if row.get("analyzed_at"):
        meta.append(f"analyzed {_when(row.get('analyzed_at'))}")
    if row.get("provider"):
        meta.append(f"data: {row['provider']}")
    if row.get("mock_mode"):
        meta.append("mock data")
    flow: list[Any] = [
        Paragraph(_pdf_text(row.get("keyword", "")), st["h1"]),
        Paragraph(_pdf_text(" · ".join(meta)), st["muted"]),
        Spacer(1, 6),
        Paragraph(f"{_verdict_markup(verdict)} &nbsp; {_pdf_text(verdict.get('reason', ''))}", st["body"]),
    ]
    if row.get("rescored"):
        flow.append(Paragraph("Older analysis: numbers recalculated with the current click model.", st["small"]))

    clicks_text = _num(mid) if mid is not None else f"{s.get('organic_ctr_total', 0)}%"
    clicks_note = (f"range {_num(low)}-{_num(high)}" if mid is not None and low != high
                   else "of searches click organic" if mid is None else "organic, page one")
    stats = [
        ("Capturable clicks / month", clicks_text, clicks_note),
        ("#1 ranking worth", _num(verdict.get("top1_clicks")), "clicks / month"),
        ("Top 3 combined", _num(verdict.get("top3_clicks")), "clicks / month"),
        ("Clicks lost to SERP features", f"{s.get('penalty_percent', 0)}%", "vs a page of only organic links"),
        ("Monthly searches", _num(row.get("raw_volume")) if _has_volume(row) else "-",
         VOLUME_LABELS.get(row.get("volume_source") or "unknown", "")),
    ]
    stat_table = Table(
        [[Paragraph(_pdf_text(label), st["cell_head"]) for label, _, _ in stats],
         [Paragraph(_pdf_text(value), st["big"]) for _, value, _ in stats],
         [Paragraph(_pdf_text(note), st["small"]) for _, _, note in stats]],
        colWidths=[CONTENT_WIDTH / 5] * 5,
    )
    stat_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    flow += [Spacer(1, 8), stat_table]

    recs = rep.get("recommendations")
    if recs is not None:
        flow.append(Paragraph("What to do", st["h2"]))
        if recs:
            for rec in recs:
                flow.append(Paragraph(f"<b>{_pdf_text(rec['title'])}.</b> {_pdf_text(rec['detail'])}", st["body"], bulletText="•"))
        else:
            flow.append(Paragraph("A plain results page: nothing special to plan around. Focus on ranking well.", st["body"]))

    positions = rep.get("page_one") or [{**p, "domain": None} for p in (rep.get("click_model") or {}).get("positions") or []]
    page_one: list[Any] = [Paragraph("Page one", st["h2"])]
    costly, neutral = _features(row)
    if costly or neutral:
        parts = ([f"<b>Reduce clicks:</b> {_pdf_text('; '.join(costly))}"] if costly else []) + \
                ([f"<b>Also present:</b> {_pdf_text(', '.join(neutral))}"] if neutral else [])
        page_one.append(Paragraph(" &nbsp; ".join(parts), st["muted"]))
        page_one.append(Spacer(1, 4))
    if positions:
        known = _has_volume(row)
        head = ["#", "Site", "Clicks / month" if known else "Share of searches"]
        data = [[Paragraph(h, st["cell_head"]) for h in head]]
        for p in positions:
            value = (_num(p.get("clicks")) + ("*" if p.get("clicks_low") != p.get("clicks_high") else "")) if known else f"{p.get('ctr') or 0:.1f}%"
            data.append([Paragraph(str(p.get("position")), st["cell"]),
                         Paragraph(_pdf_text(p.get("domain") or f"Position {p.get('position')}"), st["cell"]),
                         Paragraph(value, st["cell"])])
        table = Table(data, colWidths=[10 * mm, CONTENT_WIDTH - 50 * mm, 40 * mm])
        table.setStyle(_GRID)
        page_one.append(table)
        if known and any(p.get("clicks_low") != p.get("clicks_high") for p in positions):
            page_one.append(Paragraph("* Middle of a range: several features overlap at this position.", st["small"]))
    else:
        page_one.append(Paragraph("No organic results on page one.", st["body"]))
    flow.append(KeepTogether(page_one))

    changes = row.get("changes") or {}
    if changes.get("has_previous") and changes.get("has_changes"):
        flow.append(Paragraph(f"What changed since {_pdf_text(_when(changes.get('previous_fetched_at')))}", st["h2"]))
        for line in changes.get("summary") or []:
            flow.append(Paragraph(_pdf_text(line), st["body"], bulletText="•"))

    model = rep.get("click_model") or {}
    sources = [f"{f['label']}: {f['confidence']} confidence ({f['source']})" for f in model.get("factors") or []]
    baseline = (model.get("baseline_source") or {}).get("name")
    note = "How this was estimated: " + ("; ".join(sources) + ". " if sources else "") + \
           (f"Baseline click rates: {baseline}. " if baseline else "") + f"Full methodology: {METHODOLOGY_URL}"
    flow += [Spacer(1, 10), Paragraph(_pdf_text(note), st["small"])]
    return flow


def generate_pdf(rows: list[dict[str, Any]]) -> bytes:
    st = _styles()
    generated = datetime.now(timezone.utc).strftime("%d %b %Y")
    order = ranked(rows)
    flow: list[Any] = []
    if len(order) > 1:
        flow += _summary_page(order, st, generated)
    for i, row in enumerate(order):
        if flow:
            flow.append(PageBreak())
        flow += _keyword_page(row, st)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawString(18 * mm, 10 * mm, f"Startly Analyze · generated {generated}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
        title="Keyword opportunity report", author="Startly Analyze",
    )
    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
