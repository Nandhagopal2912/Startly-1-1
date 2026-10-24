"""Fonts for keywords in any script.

The report's own text uses Helvetica, which only covers Western European characters (cp1252). Text that
needs more, like a Hindi, Tamil, Arabic, Japanese or Polish keyword, is drawn in a font that has those
glyphs: bundled Noto fonts (fonts/, SIL Open Font License) shaped by HarfBuzz via uharfbuzz, or
ReportLab's built-in Asian fonts, which PDF viewers supply.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR = Path(__file__).resolve().parent / "fonts"

# family name -> (regular file, bold file)
_TTF = {
    "NotoSans": ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf"),
    "NotoSansDevanagari": ("NotoSansDevanagari-Regular.ttf", "NotoSansDevanagari-Bold.ttf"),
    "NotoSansTamil": ("NotoSansTamil-Regular.ttf", "NotoSansTamil-Bold.ttf"),
    "NotoSansArabic": ("NotoSansArabic-Regular.ttf", "NotoSansArabic-Bold.ttf"),
}
JAPANESE, CHINESE, KOREAN = "HeiseiKakuGo-W5", "STSong-Light", "HYGothic-Medium"

_registered = False


def register_fonts() -> None:
    global _registered
    if _registered:
        return
    for family, (regular, bold) in _TTF.items():
        pdfmetrics.registerFont(TTFont(family, str(FONT_DIR / regular)))
        pdfmetrics.registerFont(TTFont(f"{family}-Bold", str(FONT_DIR / bold)))
        # Lets <b> inside a <font name="..."> run pick the bold file.
        addMapping(family, 0, 0, family)
        addMapping(family, 1, 0, f"{family}-Bold")
        addMapping(family, 0, 1, family)
        addMapping(family, 1, 1, f"{family}-Bold")
    for cid in (JAPANESE, CHINESE, KOREAN):
        pdfmetrics.registerFont(UnicodeCIDFont(cid))
        for bold in (0, 1):
            for italic in (0, 1):
                addMapping(cid, bold, italic, cid)  # no bold cut; bold text stays regular weight
    _registered = True


def _fits_helvetica(ch: str) -> bool:
    try:
        ch.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def _script_font(ch: str, has_kana: bool) -> str | None:
    """Font for one character, or None when Helvetica can draw it."""
    if _fits_helvetica(ch):
        return None
    cp = ord(ch)
    if 0x0900 <= cp <= 0x097F or 0xA8E0 <= cp <= 0xA8FF:
        return "NotoSansDevanagari"
    if 0x0B80 <= cp <= 0x0BFF:
        return "NotoSansTamil"
    if 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0x08A0 <= cp <= 0x08FF or 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF:
        return "NotoSansArabic"
    if 0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F:
        return KOREAN
    if 0x3040 <= cp <= 0x30FF or 0x31F0 <= cp <= 0x31FF:
        return JAPANESE
    if 0x3000 <= cp <= 0x303F or 0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF or 0xFF00 <= cp <= 0xFFEF:
        return JAPANESE if has_kana else CHINESE  # Han characters: Japanese if the text also has kana
    return "NotoSans"  # Cyrillic, Greek, extended Latin and anything else Noto Sans covers


def _runs(text: str) -> list[tuple[str | None, str]]:
    """Split text into (font or None, chunk). Spaces and Western punctuation join the run they sit in,
    so "डिजिटल मार्केटिंग" stays one run instead of three."""
    has_kana = any(0x3040 <= ord(c) <= 0x30FF for c in text)
    runs: list[tuple[str | None, str]] = []
    for ch in text:
        font = _script_font(ch, has_kana)
        neutral = font is None and not ch.isalnum()
        if runs and (font == runs[-1][0] or (neutral and runs[-1][0] is not None)):
            runs[-1] = (runs[-1][0], runs[-1][1] + ch)
        else:
            runs.append((font, ch))
    return runs


def _visual(font: str | None, chunk: str) -> str:
    """HarfBuzz shapes the letters inside each word, but lines are laid out left to right, so a
    right-to-left phrase needs its word order flipped to read correctly."""
    if font == "NotoSansArabic":
        return " ".join(reversed(chunk.split(" ")))
    return chunk


def font_markup(text: str, bold: bool = False) -> str:
    """Escape text for ReportLab paragraphs, switching fonts only for the parts Helvetica can't draw.
    Pass bold=True instead of wrapping the result in <b>: a font switch inside <b> would drop the bold."""
    register_fonts()
    out = []
    for font, chunk in _runs(text):
        safe = escape(_visual(font, chunk))
        if bold:
            safe = f"<b>{safe}</b>"
        out.append(safe if font is None else f'<font name="{font}">{safe}</font>')
    return "".join(out)


def chart_text(text: str) -> str:
    """Text for a chart label, in reading order (see _visual)."""
    return "".join(_visual(font, chunk) for font, chunk in _runs(text))


def chart_font(text: str, bold: bool = False) -> str:
    """One font for a whole chart label (chart text can't switch fonts mid-string)."""
    register_fonts()
    for font, _ in _runs(text):
        if font is not None:
            if font in _TTF and bold:
                return f"{font}-Bold"
            return font
    return "Helvetica-Bold" if bold else "Helvetica"
