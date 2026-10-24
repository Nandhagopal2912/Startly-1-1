"""The PDF keyword opportunity report: cover, contents, summary with charts, how to read it,
a page per keyword, and the method and sources.
"""

from __future__ import annotations

import io
import math
from datetime import datetime, timezone
from statistics import median
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Circle, Drawing, Group, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from ctr_config import BASELINE_SOURCE, FEATURES, NEUTRAL_FEATURES
from insights import TOP3_CLICKS_LOW, TOP3_CLICKS_WORTH
from report_data import (
    METHODOLOGY_URL,
    VOLUME_LABELS,
    clicks,
    features,
    has_volume,
    positions,
    ranked,
    report,
    search_split,
    summary,
    verdict,
    when,
)

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

INK = colors.HexColor("#0f172a")
BODY = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748b")
FAINT = colors.HexColor("#94a3b8")
RULE = colors.HexColor("#e2e8f0")
PANEL = colors.HexColor("#f8fafc")
ACCENT = colors.HexColor("#4f46e5")
ACCENT_LIGHT = colors.HexColor("#c7d2fe")
SEARCHES = colors.HexColor("#cbd5e1")
TAKEN = colors.HexColor("#fb7185")
TONES = {"good": colors.HexColor("#059669"), "neutral": colors.HexColor("#d97706"),
         "bad": colors.HexColor("#e11d48"), "unknown": colors.HexColor("#64748b")}


# --- text helpers ---

def _t(text: Any) -> str:
    """Escape for ReportLab markup and replace characters the built-in Helvetica can't draw."""
    s = str(text if text is not None else "")
    for bad, good in (("→", "to"), ("≈", "~"), ("−", "-"), ("‑", "-"), (" ", " ")):
        s = s.replace(bad, good)
    return escape(s)


def _plain(text: Any) -> str:
    """Same replacements for text drawn directly on charts (no markup)."""
    s = str(text if text is not None else "")
    for bad, good in (("→", "to"), ("≈", "~"), ("−", "-"), ("‑", "-")):
        s = s.replace(bad, good)
    return s


def _num(value: Any) -> str:
    return "-" if value is None or value == "" else f"{float(value):,.0f}"


def _short(value: float) -> str:
    """Compact axis labels: 950, 1.2K, 3.4M."""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M".replace(".0M", "M")
    if value >= 1_000:
        return f"{value / 1_000:.1f}K".replace(".0K", "K")
    return f"{value:.0f}"


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _nice_ticks(top: float, count: int = 4) -> list[float]:
    """Round axis ticks from 0 that reach at least `top`."""
    if top <= 0:
        return [0, 1]
    raw = top / count
    step = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= step * m:
            step *= m
            break
    ticks = [0.0]
    while ticks[-1] < top:
        ticks.append(ticks[-1] + step)
    return ticks


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=19, leading=23, textColor=INK, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=15, leading=19, textColor=INK, spaceAfter=2),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontSize=11, leading=14, textColor=INK, spaceBefore=12, spaceAfter=5),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=9.5, leading=13.5, textColor=BODY),
        "lead": ParagraphStyle("lead", parent=base["BodyText"], fontSize=10.5, leading=15, textColor=BODY),
        "muted": ParagraphStyle("muted", parent=base["BodyText"], fontSize=8.5, leading=11.5, textColor=MUTED),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontSize=7.5, leading=10, textColor=MUTED),
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontSize=8.5, leading=10.5, textColor=INK),
        "cell_head": ParagraphStyle("cell_head", parent=base["BodyText"], fontSize=7.5, leading=9, textColor=MUTED),
        "big": ParagraphStyle("big", parent=base["BodyText"], fontSize=15, leading=18, textColor=INK, fontName="Helvetica-Bold"),
        "toc0": ParagraphStyle("toc0", fontName="Helvetica-Bold", fontSize=10.5, leading=16, textColor=INK, leftIndent=0),
        "toc1": ParagraphStyle("toc1", fontName="Helvetica", fontSize=9.5, leading=13, textColor=BODY, leftIndent=14),
    }


def _heading(text: str, style: ParagraphStyle, toc_level: int | None = None) -> Paragraph:
    p = Paragraph(_t(text), style)
    if toc_level is not None:
        p._toc = (toc_level, text)  # picked up by ReportDoc.afterFlowable
    return p


def _verdict_markup(v: dict[str, Any]) -> str:
    color = TONES.get(v.get("tone", "unknown"), MUTED).hexval().replace("0x", "#")
    return f'<font color="{color}"><b>{_t(v.get("label", "-"))}</b></font>'


_GRID = TableStyle([
    ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#cbd5e1")),
    ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
])


# --- charts ---

def _legend(d: Drawing, x: float, y: float, items: list[tuple[colors.Color, str]]) -> None:
    for color, label in items:
        d.add(Rect(x, y - 1, 7, 7, fillColor=color, strokeColor=None))
        d.add(String(x + 10, y, label, fontName="Helvetica", fontSize=7.5, fillColor=MUTED))
        x += 18 + len(label) * 3.9


def chart_searches_vs_clicks(rows: list[dict[str, Any]], width: float = CONTENT_W) -> Drawing:
    """Each keyword's monthly searches (light) with the capturable clicks inside them (dark)."""
    data = [r for r in rows if clicks(r)[0] is not None][:12]
    label_w, value_w, row_h = 150, 92, 17
    d = Drawing(width, 18 + row_h * len(data))
    _legend(d, label_w, d.height - 9, [(ACCENT, "Capturable clicks / month"), (SEARCHES, "Monthly searches")])
    top = max((float(r["raw_volume"]) for r in data), default=1) or 1
    bar_w = width - label_w - value_w
    for i, r in enumerate(data):
        y = d.height - 22 - i * row_h - 9
        mid = float(clicks(r)[0])
        d.add(String(0, y + 2, _clip(_plain(r.get("keyword", "")), 34), fontName="Helvetica", fontSize=8, fillColor=INK))
        d.add(Rect(label_w, y, bar_w * float(r["raw_volume"]) / top, 10, fillColor=SEARCHES, strokeColor=None))
        d.add(Rect(label_w, y, bar_w * mid / top, 10, fillColor=ACCENT, strokeColor=None))
        d.add(String(label_w + bar_w + 6, y + 2, f"{mid:,.0f} of {float(r['raw_volume']):,.0f}",
                     fontName="Helvetica", fontSize=7.5, fillColor=MUTED))
    return d


def chart_opportunity_map(rows: list[dict[str, Any]], width: float = CONTENT_W, height: float = 235) -> Drawing:
    """Capturable clicks (up) against clicks lost to SERP features (right), numbered like the ranking."""
    data = [(i, r) for i, r in enumerate(rows, start=1) if clicks(r)[0] is not None]
    d = Drawing(width, height)
    left, bottom, right, top_pad = 42, 30, 10, 12
    plot_w, plot_h = width - left - right, height - bottom - top_pad
    y_ticks = _nice_ticks(max((float(clicks(r)[0]) for _, r in data), default=1) * 1.08)
    y_max = y_ticks[-1]

    def px(loss): return left + plot_w * loss / 100
    def py(value): return bottom + plot_h * value / y_max

    # Quadrants: split at 50% click loss and at the middle keyword's clicks.
    mid_clicks = median([float(clicks(r)[0]) for _, r in data]) if data else y_max / 2
    d.add(Rect(left, bottom, plot_w, plot_h, fillColor=PANEL, strokeColor=RULE, strokeWidth=0.5))
    d.add(Line(px(50), bottom, px(50), bottom + plot_h, strokeColor=FAINT, strokeWidth=0.5, strokeDashArray=[2, 2]))
    d.add(Line(left, py(mid_clicks), left + plot_w, py(mid_clicks), strokeColor=FAINT, strokeWidth=0.5, strokeDashArray=[2, 2]))
    for text, x, y, anchor in (
        ("More clicks, open page", left + 4, bottom + plot_h - 10, "start"),
        ("More clicks, Google keeps much", left + plot_w - 4, bottom + plot_h - 10, "end"),
        ("Fewer clicks, open page", left + 4, bottom + 4, "start"),
        ("Fewer clicks, crowded page", left + plot_w - 4, bottom + 4, "end"),
    ):
        d.add(String(x, y, text, fontName="Helvetica-Oblique", fontSize=7, fillColor=FAINT, textAnchor=anchor))
    for tick in y_ticks:
        d.add(Line(left - 3, py(tick), left, py(tick), strokeColor=FAINT, strokeWidth=0.5))
        d.add(String(left - 5, py(tick) - 2.5, _short(tick), fontName="Helvetica", fontSize=7, fillColor=MUTED, textAnchor="end"))
    for tick in (0, 25, 50, 75, 100):
        d.add(String(px(tick), bottom - 10, f"{tick}%", fontName="Helvetica", fontSize=7, fillColor=MUTED, textAnchor="middle"))
    d.add(String(left + plot_w / 2, 2, "Clicks lost to SERP features", fontName="Helvetica", fontSize=7.5, fillColor=MUTED, textAnchor="middle"))
    # rotate(90) turns (x, y) into (-y, x): this lands the label at x=7, centred on the plot's height.
    label = String(bottom + plot_h / 2, -7, "Capturable clicks / month", fontName="Helvetica", fontSize=7.5,
                   fillColor=MUTED, textAnchor="middle")
    rotated = Group(label)
    rotated.rotate(90)
    d.add(rotated)
    for rank, r in data:
        x, y = px(float(summary(r).get("penalty_percent") or 0)), py(float(clicks(r)[0]))
        color = TONES.get(verdict(r).get("tone", "unknown"), MUTED)
        d.add(Circle(x, y, 7, fillColor=color, strokeColor=colors.white, strokeWidth=1))
        d.add(String(x, y - 2.6, str(rank), fontName="Helvetica-Bold", fontSize=7, fillColor=colors.white, textAnchor="middle"))
    return d


def chart_search_split(row: dict[str, Any], width: float = CONTENT_W) -> Drawing:
    """What happens to 100 searches for this keyword."""
    organic, taken, other = search_split(row)
    d = Drawing(width, 46)
    x = 0.0
    for share, color in ((organic, ACCENT), (taken, TAKEN), (other, RULE)):
        w = width * share / 100
        if w > 0:
            d.add(Rect(x, 30, w, 14, fillColor=color, strokeColor=None))
        x += w
    _legend(d, 0, 14, [
        (ACCENT, f"{organic:.0f} click an organic result on page one"),
        (TAKEN, f"{taken:.0f} lost to Google's own features"),
        (RULE, f"{other:.0f} click elsewhere or don't click"),
    ])
    return d


def chart_positions(row: dict[str, Any], width: float = CONTENT_W) -> Drawing:
    """Clicks (or share of searches) each organic position should get, labelled with the site ranking there."""
    rows = positions(row)
    known = has_volume(row)
    label_w, value_w, row_h = 170, 70, 15
    d = Drawing(width, max(row_h * len(rows), 1))
    value = (lambda p: float(p.get("clicks") or 0)) if known else (lambda p: float(p.get("ctr") or 0))
    high = (lambda p: float(p.get("clicks_high") or 0)) if known else (lambda p: float(p.get("ctr_high") or p.get("ctr") or 0))
    top = max([high(p) for p in rows] + [1])
    bar_w = width - label_w - value_w
    for i, p in enumerate(rows):
        y = d.height - (i + 1) * row_h + 3
        name = f"#{p.get('position')}  {p.get('domain') or 'Position ' + str(p.get('position'))}"
        d.add(String(0, y + 1.5, _clip(_plain(name), 40), fontName="Helvetica", fontSize=8, fillColor=INK))
        if high(p) > value(p):
            d.add(Rect(label_w, y, bar_w * high(p) / top, 9, fillColor=ACCENT_LIGHT, strokeColor=None))
        d.add(Rect(label_w, y, bar_w * value(p) / top, 9, fillColor=ACCENT, strokeColor=None))
        text = f"{value(p):,.0f} clicks" if known else f"{value(p):.1f}% of searches"
        d.add(String(label_w + bar_w + 6, y + 1.5, text, fontName="Helvetica", fontSize=7.5, fillColor=MUTED))
    return d


def chart_before_after(changes: dict[str, Any], width: float = CONTENT_W) -> Drawing | None:
    before, after = changes.get("clicks_before"), changes.get("clicks_after")
    unit = "clicks / month"
    if before is None or after is None:
        before, after, unit = changes.get("ctr_before"), changes.get("ctr_after"), "% of searches"
    if before is None or after is None:
        return None
    label_w, value_w = 120, 110
    d = Drawing(width, 36)
    top = max(float(before), float(after), 1)
    bar_w = width - label_w - value_w
    for i, (label, value, color) in enumerate((
        (f"Before ({when(changes.get('previous_fetched_at'))})", float(before), SEARCHES),
        (f"Now ({when(changes.get('current_fetched_at'))})", float(after), ACCENT),
    )):
        y = 22 - i * 17
        d.add(String(0, y + 1.5, label, fontName="Helvetica", fontSize=8, fillColor=INK))
        d.add(Rect(label_w, y, bar_w * value / top, 10, fillColor=color, strokeColor=None))
        shown = f"{value:,.0f} {unit}" if unit.startswith("clicks") else f"{value:.1f}{unit}"
        d.add(String(label_w + bar_w * value / top + 6, y + 1.5, shown, fontName="Helvetica", fontSize=7.5, fillColor=MUTED))
    return d


# --- document ---

class ReportDoc(BaseDocTemplate):
    """Cover page without footer, content pages with footer; headings feed the contents and PDF outline."""

    def __init__(self, buffer: io.BytesIO, cover_painter, footer_text: str):
        super().__init__(buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=16 * mm,
                         bottomMargin=18 * mm, title="Keyword opportunity report", author="Startly Analyze")
        frame = Frame(MARGIN, 18 * mm, CONTENT_W, PAGE_H - 34 * mm, id="body", leftPadding=0, rightPadding=0)
        self.footer_text = footer_text
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[frame], onPage=cover_painter),
            PageTemplate(id="content", frames=[frame], onPage=self._footer),
        ])

    def _footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(FAINT)
        canvas.drawString(MARGIN, 10 * mm, self.footer_text)
        canvas.drawRightString(PAGE_W - MARGIN, 10 * mm, f"Page {doc.page}")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN, 13.5 * mm, PAGE_W - MARGIN, 13.5 * mm)
        canvas.restoreState()

    def afterFlowable(self, flowable):
        toc = getattr(flowable, "_toc", None)
        if toc:
            level, text = toc
            key = f"h{id(flowable)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
            self.notify("TOCEntry", (level, text, self.page, key))


def _headline(order: list[dict[str, Any]]) -> list[tuple[str, str]]:
    with_volume = [r for r in order if clicks(r)[0] is not None]
    searches = sum(float(r["raw_volume"]) for r in with_volume)
    capture = sum(float(clicks(r)[0]) for r in with_volume)
    lost = (sum(float(summary(r).get("penalty_percent") or 0) * float(r["raw_volume"]) for r in with_volume) / searches) if searches else None
    best = with_volume[0]["keyword"] if with_volume else (order[0]["keyword"] if order else "-")
    return [
        ("Monthly searches", _num(searches) if with_volume else "-"),
        ("Capturable clicks / month", _num(capture) if with_volume else "-"),
        ("Clicks lost to SERP features", f"{lost:.0f}%" if lost is not None else "-"),
        ("Top opportunity", _clip(best, 26)),
    ]


def _cover_painter(order: list[dict[str, Any]], generated: str):
    countries = sorted({r.get("location_name") or "United States" for r in order})
    headline = _headline(order)
    scope = f"{len(order)} keyword{'s' if len(order) != 1 else ''} · {', '.join(countries)}"

    def paint(canvas, doc):
        canvas.saveState()
        band = 118 * mm
        canvas.setFillColor(ACCENT)
        canvas.rect(0, PAGE_H - band, PAGE_W, band, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(MARGIN, PAGE_H - 26 * mm, "STARTLY ANALYZE")
        canvas.setFont("Helvetica-Bold", 30)
        canvas.drawString(MARGIN, PAGE_H - 62 * mm, "Keyword opportunity")
        canvas.drawString(MARGIN, PAGE_H - 75 * mm, "report")
        canvas.setFont("Helvetica", 11.5)
        canvas.drawString(MARGIN, PAGE_H - 90 * mm, _plain(scope))
        canvas.drawString(MARGIN, PAGE_H - 97 * mm, f"Generated {generated}")
        # Headline numbers
        box_w, box_h, gap = (CONTENT_W - 3 * 4 * mm) / 4, 26 * mm, 4 * mm
        y = PAGE_H - band - 18 * mm - box_h
        for i, (label, value) in enumerate(headline):
            x = MARGIN + i * (box_w + gap)
            canvas.setFillColor(PANEL)
            canvas.setStrokeColor(RULE)
            canvas.roundRect(x, y, box_w, box_h, 3 * mm, stroke=1, fill=1)
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 7.5)
            canvas.drawString(x + 4 * mm, y + box_h - 7 * mm, label)
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 15 if len(value) < 12 else 10)
            canvas.drawString(x + 4 * mm, y + 7 * mm, _plain(value))
        canvas.setFillColor(BODY)
        canvas.setFont("Helvetica", 10)
        text = canvas.beginText(MARGIN, y - 16 * mm)
        text.setLeading(14.5)
        for line in (
            "Search volume overstates traffic. Google's AI Overviews, ads, maps and other features",
            "take a share of the clicks before anyone reaches the organic results.",
            "",
            "This report estimates the clicks that are actually left for organic results on page one,",
            "what each ranking position is worth, who ranks today, and what to do about it.",
        ):
            text.textLine(line)
        canvas.drawText(text)
        canvas.setFillColor(FAINT)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(MARGIN, 14 * mm, "Estimates use published click-through-rate research. See \"Method and sources\" at the end.")
        canvas.restoreState()

    return paint


def _findings(order: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    with_volume = [r for r in order if clicks(r)[0] is not None]
    if with_volume:
        best = with_volume[0]
        v = verdict(best)
        out.append(f"<b>Best opportunity: {_t(best['keyword'])}.</b> About {_num(clicks(best)[0])} capturable clicks a month; "
                   f"a #1 ranking is worth about {_num(v.get('top1_clicks'))}.")
        searches = sum(float(r["raw_volume"]) for r in with_volume)
        capture = sum(float(clicks(r)[0]) for r in with_volume)
        out.append(f"Across {len(with_volume)} keyword{'s' if len(with_volume) != 1 else ''} with known volume, "
                   f"{_num(searches)} monthly searches turn into about {_num(capture)} capturable clicks "
                   f"({capture / searches * 100:.0f}%).")
    counts: dict[str, int] = {}
    for r in order:
        label = verdict(r).get("label")
        if label:
            counts[label] = counts.get(label, 0) + 1
    if counts:
        out.append("Verdicts: " + ", ".join(f"{n} {_t(label.lower())}" for label, n in counts.items()) + ".")
    hostile = [r for r in order if (summary(r).get("penalty_percent") or 0) >= 50]
    if hostile:
        worst = max(hostile, key=lambda r: summary(r).get("penalty_percent") or 0)
        out.append(f"<b>Google keeps the most on {_t(worst['keyword'])}:</b> SERP features take about "
                   f"{summary(worst).get('penalty_percent')}% of its organic clicks"
                   + (f" ({len(hostile)} keywords lose half or more)." if len(hostile) > 1 else "."))
    aio = [r for r in order if "ai_overview" in (summary(r).get("non_organic_types") or [])]
    if aio:
        out.append(f"An AI Overview appears on {len(aio)} of {len(order)} keyword{'s' if len(order) != 1 else ''}.")
    missing = [r["keyword"] for r in order if not has_volume(r)]
    if missing:
        out.append(f"<b>Needs a monthly volume:</b> {_t(', '.join(missing))}. Until then only click-through shares are shown.")
    return out


def _summary_section(order: list[dict[str, Any]], st: dict[str, ParagraphStyle]) -> list[Any]:
    flow: list[Any] = [_heading("Summary", st["h1"], 0)]
    flow += [Paragraph(f, st["body"], bulletText="•") for f in _findings(order)]
    head = ["#", "Keyword", "Verdict", "Clicks / month", "#1 worth", "Clicks lost", "Searches"]
    data = [[Paragraph(h, st["cell_head"]) for h in head]]
    for i, row in enumerate(order, start=1):
        v = verdict(row)
        mid, low, high = clicks(row)
        shown = _num(mid) + (f"<br/><font size=7 color='#64748b'>{_num(low)}-{_num(high)}</font>" if mid is not None and low != high else "")
        data.append([
            Paragraph(str(i), st["cell"]), Paragraph(f"<b>{_t(row.get('keyword', ''))}</b>", st["cell"]),
            Paragraph(_verdict_markup(v), st["cell"]), Paragraph(shown, st["cell"]),
            Paragraph(_num(v.get("top1_clicks")), st["cell"]),
            Paragraph(f"{summary(row).get('penalty_percent', 0)}%", st["cell"]),
            Paragraph(_num(row.get("raw_volume")) if has_volume(row) else "-", st["cell"]),
        ])
    table = Table(data, colWidths=[8 * mm, 54 * mm, 34 * mm, 24 * mm, 18 * mm, 18 * mm, 18 * mm], repeatRows=1)
    table.setStyle(_GRID)
    flow += [Paragraph("All keywords, ranked", st["h3"]), table]
    if any(clicks(r)[0] is not None for r in order):
        flow += [
            Paragraph("Searches vs clicks you can capture", st["h3"]),
            Paragraph("The light bar is all monthly searches; the dark part is what's left for organic results on page one.", st["muted"]),
            Spacer(1, 4), chart_searches_vs_clicks(order),
        ]
        flow += [KeepTogether([
            Paragraph("Opportunity map", st["h3"]),
            Paragraph("Each dot is a keyword, numbered as in the ranking above and colored by verdict. Up means more clicks; "
                      "right means Google's own features take more of them. The best targets sit top left.", st["muted"]),
            Spacer(1, 4), chart_opportunity_map(order),
        ])]
    return flow


def _how_to_read(st: dict[str, ParagraphStyle]) -> list[Any]:
    terms = [
        ("Monthly searches", "How often the keyword is searched in a month, entered by you or from a data provider. Click counts scale with it."),
        ("Capturable clicks", "Monthly searches expected to click an organic result on page one, after Google's features take their share."),
        ("Range", "When several features overlap at a position, their combined effect is uncertain. The low end assumes their effects stack, "
                  "the high end assumes only the strongest applies, and the estimate is the middle."),
        ("#1 ranking worth / Top 3", "Clicks a month for ranking first, and for the first three positions combined."),
        ("Clicks lost to SERP features", "How many fewer organic clicks this page sends than a page with only organic links would."),
        ("Verdict", f"<b>Worth targeting:</b> the top 3 are worth {TOP3_CLICKS_WORTH:,}+ clicks a month. "
                    f"<b>Modest opportunity:</b> {TOP3_CLICKS_LOW}-{TOP3_CLICKS_WORTH - 1}. <b>Low traffic potential:</b> under {TOP3_CLICKS_LOW}. "
                    "<b>Add volume to decide:</b> the monthly searches are unknown. The thresholds are a product choice, not a measured value."),
        ("SERP features", "Everything on Google's first page that isn't a classic organic link: AI Overviews, ads, maps, image packs, "
                          "People Also Ask, videos and more. Only some of them measurably reduce organic clicks."),
    ]
    data = [[Paragraph(f"<b>{_t(term)}</b>", st["cell"]), Paragraph(text if "<b>" in text else _t(text), st["body"])] for term, text in terms]
    table = Table(data, colWidths=[42 * mm, CONTENT_W - 42 * mm])
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return [
        _heading("How to read this report", st["h1"], 0),
        Paragraph("The numbers are estimates built from published click-through-rate research, applied to what Google showed for each "
                  "keyword when it was checked. They are most reliable for <b>comparing keywords</b>, because the same assumptions apply to all of them.",
                  st["lead"]),
        Spacer(1, 8), table,
    ]


def _keyword_section(row: dict[str, Any], st: dict[str, ParagraphStyle]) -> list[Any]:
    rep, s, v = report(row), summary(row), verdict(row)
    mid, low, high = clicks(row)
    meta = [row.get("location_name") or "United States"]
    if row.get("analyzed_at"):
        meta.append(f"checked {when(row.get('analyzed_at'))}")
    if row.get("provider"):
        meta.append(f"data: {row['provider']}")
    if row.get("mock_mode"):
        meta.append("mock data")
    flow: list[Any] = [
        _heading(row.get("keyword", ""), st["h2"], 1),
        Paragraph(_t(" · ".join(meta)), st["muted"]),
        Spacer(1, 6),
        Paragraph(f"{_verdict_markup(v)} &nbsp; {_t(v.get('reason', ''))}", st["body"]),
    ]
    if row.get("rescored"):
        flow.append(Paragraph("Older analysis: numbers recalculated with the current click model.", st["small"]))

    stats = [
        ("Capturable clicks / month", _num(mid) if mid is not None else f"{float(s.get('organic_ctr_total') or 0):.1f}%",
         f"range {_num(low)}-{_num(high)}" if mid is not None and low != high else ("of searches click organic" if mid is None else "organic, page one")),
        ("#1 ranking worth", _num(v.get("top1_clicks")), "clicks / month"),
        ("Top 3 combined", _num(v.get("top3_clicks")), "clicks / month"),
        ("Clicks lost to SERP features", f"{s.get('penalty_percent', 0)}%", "vs only organic links"),
        ("Monthly searches", _num(row.get("raw_volume")) if has_volume(row) else "-", VOLUME_LABELS.get(row.get("volume_source") or "unknown", "")),
    ]
    stat_table = Table(
        [[Paragraph(_t(a), st["cell_head"]) for a, _, _ in stats],
         [Paragraph(_t(b), st["big"]) for _, b, _ in stats],
         [Paragraph(_t(c), st["small"]) for _, _, c in stats]],
        colWidths=[CONTENT_W / 5] * 5)
    stat_table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, RULE), ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                                    ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    flow += [Spacer(1, 8), stat_table]

    flow += [KeepTogether([Paragraph("Where 100 searches go", st["h3"]), chart_search_split(row)])]

    recs = rep.get("recommendations")
    if recs is not None:
        flow.append(Paragraph("What to do", st["h3"]))
        if recs:
            flow += [Paragraph(f"<b>{_t(r['title'])}.</b> {_t(r['detail'])}", st["body"], bulletText="•") for r in recs]
        else:
            flow.append(Paragraph("A plain results page: nothing special to plan around. Focus on ranking well.", st["body"]))

    rows = positions(row)
    page_one: list[Any] = [Paragraph("Who ranks, and what each position is worth", st["h3"])]
    costly, neutral = features(row)
    if costly or neutral:
        parts = ([f"<b>Reduce clicks:</b> {_t('; '.join(costly))}"] if costly else []) + \
                ([f"<b>Also on the page:</b> {_t(', '.join(neutral))}"] if neutral else [])
        page_one += [Paragraph(" &nbsp; ".join(parts), st["muted"]), Spacer(1, 4)]
    if rows:
        page_one.append(chart_positions(row))
        if has_volume(row) and any(p.get("clicks_low") != p.get("clicks_high") for p in rows):
            page_one.append(Paragraph("The lighter bar shows the high end of the range where features overlap.", st["small"]))
    else:
        page_one.append(Paragraph("No organic results on page one.", st["body"]))
    flow.append(KeepTogether(page_one))

    changes = row.get("changes") or {}
    if changes.get("has_previous") and changes.get("has_changes"):
        block: list[Any] = [Paragraph(f"What changed since {_t(when(changes.get('previous_fetched_at')))}", st["h3"])]
        chart = chart_before_after(changes)
        if chart:
            block += [chart, Spacer(1, 4)]
        flow.append(KeepTogether(block))
        flow += [Paragraph(_t(line), st["body"], bulletText="•") for line in changes.get("summary") or []]
    return flow


def _method_section(st: dict[str, ParagraphStyle]) -> list[Any]:
    head = ["Feature", "Effect at #1", "Confidence", "Source"]
    data = [[Paragraph(h, st["cell_head"]) for h in head]]
    for f in FEATURES.values():
        data.append([Paragraph(f"<b>{_t(f['label'])}</b>", st["cell"]),
                     Paragraph(f"{round((f['multipliers'][0] - 1) * 100)}%", st["cell"]),
                     Paragraph(_t(f["confidence"]), st["cell"]), Paragraph(_t(f["source"]), st["small"])])
    table = Table(data, colWidths=[30 * mm, 20 * mm, 20 * mm, CONTENT_W - 70 * mm], repeatRows=1)
    table.setStyle(_GRID)
    neutral = ", ".join(t.replace("_", " ") for t in NEUTRAL_FEATURES)
    limits = [
        "The curves are averages of millions of results pages; a single keyword can differ by 2x or more.",
        "Click counts scale directly with the monthly search volume you provide.",
        "The ads effect comes from a 2014 study and is marked low confidence.",
        "The studies are observational: pages with AI Overviews may differ in other ways too.",
        "The report says what a position is worth, not how hard it is to reach.",
    ]
    return [
        _heading("Method and sources", st["h1"], 0),
        Paragraph("For each keyword, Startly reads Google's first page and counts the organic results and the features shown. "
                  "It starts from the share of searches that click each organic position on an average page, then reduces the positions "
                  "that measured features affect. Where several features overlap, it gives a range: effects stacked (low) and only the "
                  "strongest effect (high), with the middle as the estimate.", st["body"]),
        Spacer(1, 6),
        Paragraph(f"<b>Baseline click rates:</b> {_t(BASELINE_SOURCE['name'])} ({_t(BASELINE_SOURCE['url'])}).", st["body"]),
        Paragraph("Features that reduce organic clicks", st["h3"]), table,
        Spacer(1, 4),
        Paragraph(f"No penalty, because the data shows none or isn't reliable yet: {_t(neutral)}.", st["muted"]),
        Paragraph("Limitations", st["h3"]),
        *[Paragraph(_t(line), st["body"], bulletText="•") for line in limits],
        Spacer(1, 8),
        Paragraph(f"Full methodology, numbers and sources: {_t(METHODOLOGY_URL)}", st["muted"]),
    ]


def generate_pdf(rows: list[dict[str, Any]]) -> bytes:
    st = _styles()
    generated = datetime.now(timezone.utc).strftime("%d %b %Y")
    order = ranked(rows)
    multi = len(order) > 1

    story: list[Any] = [NextPageTemplate("content"), PageBreak()]  # page 1 is the painted cover
    if multi:
        toc = TableOfContents()
        toc.levelStyles = [st["toc0"], st["toc1"]]
        story += [Paragraph("Contents", st["h1"]), Spacer(1, 6), toc, PageBreak()]
        story += _summary_section(order, st) + [PageBreak()]
    story += _how_to_read(st)
    for i, row in enumerate(order):
        story.append(PageBreak())
        if i == 0:
            story += [_heading("Keyword details", st["h1"], 0),
                      Paragraph("One page per keyword, in ranked order.", st["muted"]), Spacer(1, 10)]
        story += _keyword_section(row, st)
    story += [PageBreak()] + _method_section(st)

    buffer = io.BytesIO()
    doc = ReportDoc(buffer, _cover_painter(order, generated), f"Startly Analyze · Keyword opportunity report · {generated}")
    doc.multiBuild(story)  # two passes so the contents can list page numbers
    return buffer.getvalue()
