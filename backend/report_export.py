"""CSV/PDF export matching the analysis UI: KPIs, charts, narrative sections."""

from __future__ import annotations

import csv
import io
from typing import Any

from reportlab.graphics import renderPDF
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def generate_csv_detailed(rows: list[dict[str, Any]]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Traffic Opportunity — Full Export"])
    writer.writerow([])
    writer.writerow(
        [
            "SUMMARY (same KPIs as analysis page cards)",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    writer.writerow(
        [
            "Keyword",
            "Raw volume",
            "Adjusted volume",
            "Saturation score (0–1)",
            "Saturation %",
            "Organic results",
            "Non-organic count",
            "Total SERP items",
            "Penalty applied",
            "Penalty %",
            "Penalty factor",
            "Volume reduction",
            "Demand / organic slot",
            "Saturation label",
            "Source",
            "Mock mode",
        ]
    )

    for row in rows:
        rep = row.get("report") or {}
        summary = rep.get("summary") or {}
        writer.writerow(
            [
                row.get("keyword", summary.get("keyword", "")),
                summary.get("raw_volume", row.get("raw_volume", "")),
                summary.get("adjusted_volume", row.get("adjusted_volume", "")),
                summary.get("saturation_score", row.get("saturation_score", "")),
                summary.get("saturation_percent", ""),
                summary.get("organic_results", row.get("organic_results", "")),
                summary.get("non_organic_count", ""),
                summary.get("total_results", row.get("total_results", "")),
                summary.get("penalty_applied", row.get("penalty_applied", "")),
                summary.get("penalty_percent", ""),
                summary.get("penalty_factor", ""),
                summary.get("volume_reduction", ""),
                summary.get("demand_per_organic_slot", ""),
                summary.get("saturation_label", ""),
                row.get("source", ""),
                row.get("mock_mode", ""),
            ]
        )

    writer.writerow([])
    writer.writerow(["SERP TYPE BREAKDOWN (chart data — counts per type)"])
    writer.writerow(["Keyword", "SERP type", "Count"])
    for row in rows:
        rep = row.get("report") or {}
        summary = rep.get("summary") or {}
        kw = row.get("keyword", summary.get("keyword", ""))
        breakdown = summary.get("type_breakdown") or {}
        if isinstance(breakdown, dict) and breakdown:
            for t, c in sorted(breakdown.items(), key=lambda x: (-x[1], x[0])):
                writer.writerow([kw, t, c])
        else:
            writer.writerow([kw, "(no breakdown)", ""])

    writer.writerow([])
    writer.writerow(["DETAILED SECTIONS (same text as analysis page)"])
    writer.writerow(["Keyword", "Section title", "Body"])
    for row in rows:
        rep = row.get("report") or {}
        summary = rep.get("summary") or {}
        kw = row.get("keyword", summary.get("keyword", ""))
        for sec in rep.get("sections") or []:
            if isinstance(sec, dict):
                writer.writerow([kw, sec.get("title", ""), sec.get("body", "")])

    writer.writerow([])
    writer.writerow(["COMPARE KEYWORDS CHART (raw vs adjusted vs organic slots)"])
    writer.writerow(["Keyword", "Raw volume", "Adjusted volume", "Organic slots (supply)"])
    for row in rows:
        rep = row.get("report") or {}
        summary = rep.get("summary") or {}
        writer.writerow(
            [
                row.get("keyword", summary.get("keyword", "")),
                summary.get("raw_volume", row.get("raw_volume", "")),
                summary.get("adjusted_volume", row.get("adjusted_volume", "")),
                summary.get("organic_results", row.get("organic_results", "")),
            ]
        )

    return output.getvalue().encode("utf-8")


def _drawing_raw_vs_adjusted(raw: float, adj: float) -> Drawing:
    d = Drawing(280, 160)
    bc = VerticalBarChart()
    bc.x = 40
    bc.y = 35
    bc.height = 90
    bc.width = 200
    bc.data = [[float(raw), float(adj)]]
    bc.categoryAxis.categoryNames = ["Raw volume", "Adjusted"]
    bc.categoryAxis.labels.angle = 0
    bc.categoryAxis.labels.fontSize = 8
    bc.valueAxis.valueMin = 0
    bc.valueAxis.labels.fontSize = 8
    bc.bars[0].fillColor = colors.HexColor("#3b82f6")
    d.add(bc)
    return d


def _drawing_organic_split(organic: int, other: int) -> Drawing:
    d = Drawing(200, 140)
    pc = Pie()
    pc.x = 45
    pc.y = 15
    pc.width = 90
    pc.height = 90
    pc.data = [organic, other]
    pc.labels = ["Organic", "Other"]
    pc.slices.strokeWidth = 0.25
    d.add(pc)
    return d


def _drawing_type_pie(breakdown: dict[str, int]) -> Drawing | None:
    if not breakdown:
        return None
    items = sorted(breakdown.items(), key=lambda x: -x[1])
    labels = [k[:18] + ("…" if len(k) > 18 else "") for k, _ in items]
    data = [float(v) for _, v in items]
    d = Drawing(260, 150)
    pc = Pie()
    pc.x = 10
    pc.y = 10
    pc.width = 100
    pc.height = 100
    pc.data = data
    pc.labels = labels
    pc.slices.strokeWidth = 0.25
    d.add(pc)
    return d


def generate_pdf_detailed(rows: list[dict[str, Any]]) -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    left = 40
    content_w = width - 2 * left

    for idx, row in enumerate(rows):
        if idx > 0:
            p.showPage()

        rep = row.get("report") or {}
        summary = rep.get("summary") or {}
        kw = str(row.get("keyword", summary.get("keyword", "—")))

        y = height - 48
        p.setFont("Helvetica-Bold", 16)
        p.drawString(left, y, "Traffic Opportunity Report")
        y -= 22
        p.setFont("Helvetica", 10)
        p.drawString(left, y, f"Keyword: {kw}")
        y -= 14
        src = row.get("source", "")
        mock = row.get("mock_mode", False)
        p.drawString(left, y, f"Source: {src}  ·  {'Mock data' if mock else 'Live API'}")
        y -= 28

        if not summary:
            p.setFont("Helvetica", 10)
            p.drawString(
                left,
                y,
                f"Raw: {row.get('raw_volume')}  Adjusted: {row.get('adjusted_volume')}  Saturation: {row.get('saturation_score')}",
            )
            continue

        raw_v = float(summary.get("raw_volume", 0))
        adj_v = float(summary.get("adjusted_volume", 0))
        org = int(summary.get("organic_results", 0))
        non_org = int(summary.get("non_organic_count", 0))
        total = int(summary.get("total_results", 0))

        p.setFont("Helvetica-Bold", 11)
        p.drawString(left, y, "KPI summary (same as analysis cards)")
        y -= 16

        card_w = (content_w - 24) / 4
        card_h = 52
        cards = [
            ("Raw monthly volume", f"{raw_v:,.0f}"),
            ("Adjusted volume", f"{adj_v:,.0f}"),
            (
                "Saturation score",
                f"{float(summary.get('saturation_percent', 0)):.1f}% ({org}/{total} organic)",
            ),
            (
                "Demand / organic slot",
                f"{summary.get('demand_per_organic_slot') if summary.get('demand_per_organic_slot') is not None else '—'}",
            ),
        ]
        cx = left
        for title, val in cards:
            p.setStrokeColorRGB(0.85, 0.88, 0.92)
            p.setFillColorRGB(0.97, 0.98, 0.99)
            p.roundRect(cx, y - card_h, card_w, card_h, 4, stroke=1, fill=1)
            p.setFillColorRGB(0.2, 0.2, 0.22)
            p.setFont("Helvetica", 7)
            p.drawString(cx + 6, y - 14, title[:42])
            p.setFont("Helvetica-Bold", 11)
            p.drawString(cx + 6, y - 34, str(val)[:36])
            cx += card_w + 8
        y -= card_h + 18

        p.setFont("Helvetica-Bold", 11)
        p.drawString(left, y, "Charts (same data as analysis page)")
        y -= 16

        chart_titles_y = y
        p.setFont("Helvetica", 8)
        p.drawString(left, chart_titles_y, "Raw vs adjusted demand")
        p.drawString(left + 300, chart_titles_y, "Organic vs non-organic (items)")
        d1 = _drawing_raw_vs_adjusted(raw_v, adj_v)
        d2 = _drawing_organic_split(org, non_org)
        h1 = 160
        h2 = 140
        renderPDF.draw(d1, p, left, chart_titles_y - h1)
        renderPDF.draw(d2, p, left + 280, chart_titles_y - h2)
        y = chart_titles_y - max(h1, h2) - 12

        d3 = _drawing_type_pie(summary.get("type_breakdown") or {})
        if d3:
            p.setFont("Helvetica", 8)
            p.drawString(left, y, "SERP types (full breakdown)")
            y -= 12
            renderPDF.draw(d3, p, left, y - 150)
            y -= 160
        else:
            y -= 4

        p.setFont("Helvetica-Bold", 11)
        p.drawString(left, y, "Quick numbers")
        y -= 14
        p.setFont("Helvetica", 9)
        penalty_line = (
            f"Penalty: {summary.get('penalty_percent', 0)}%  ·  Factor: {summary.get('penalty_factor', 1)}  ·  "
            f"Volume reduction: {summary.get('volume_reduction', 0)}"
        )
        for line in [
            penalty_line,
            f"Non-organic types: {', '.join(summary.get('non_organic_types') or []) or '—'}",
            f"Saturation label: {summary.get('saturation_label', '')}",
        ]:
            p.drawString(left, y, line[:120])
            y -= 12
        y -= 8

        if y < 120:
            p.showPage()
            y = height - 48

        p.setFont("Helvetica-Bold", 11)
        p.drawString(left, y, "Detailed explanation")
        y -= 14
        p.setFont("Helvetica", 9)
        for sec in rep.get("sections") or []:
            if not isinstance(sec, dict):
                continue
            title = str(sec.get("title", ""))
            body = str(sec.get("body", ""))
            if y < 80:
                p.showPage()
                y = height - 48
                p.setFont("Helvetica-Bold", 11)
                p.drawString(left, y, "Detailed explanation (continued)")
                y -= 16
                p.setFont("Helvetica", 9)
            p.setFont("Helvetica-Bold", 9)
            p.drawString(left, y, title)
            y -= 11
            p.setFont("Helvetica", 9)
            for para in _wrap_text(body, int(content_w / 4.5)):
                if y < 52:
                    p.showPage()
                    y = height - 48
                    p.setFont("Helvetica", 9)
                p.drawString(left, y, para)
                y -= 11
            y -= 6

    p.save()
    return buffer.getvalue()


def _wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    length = 0
    for w in words:
        add = len(w) + (1 if cur else 0)
        if length + add > max_chars and cur:
            lines.append(" ".join(cur))
            cur = [w]
            length = len(w)
        else:
            cur.append(w)
            length += add
    if cur:
        lines.append(" ".join(cur))
    return lines if lines else [""]
