"""Reading dashboard rows for exports (shared by the CSV and PDF reports)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ctr_config import BASELINE_CTR

VOLUME_LABELS = {"user": "Entered by user", "dataforseo": "DataForSEO", "mock": "Mock data", "api": "API", "unknown": "Unknown"}
METHODOLOGY_URL = "https://github.com/Nandhagopal2912/Startly-1-1/blob/main/METHODOLOGY.md"


def report(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("report") or {}


def summary(row: dict[str, Any]) -> dict[str, Any]:
    return report(row).get("summary") or {}


def verdict(row: dict[str, Any]) -> dict[str, Any]:
    return report(row).get("verdict") or {}


def has_volume(row: dict[str, Any]) -> bool:
    return (row.get("volume_source") or "") not in ("unknown", "")


def clicks(row: dict[str, Any]) -> tuple[Any, Any, Any]:
    """(estimate, low, high) capturable clicks, or Nones when the volume is unknown."""
    if not has_volume(row):
        return None, None, None
    s = summary(row)
    return (
        row.get("capturable_clicks", s.get("capturable_clicks")),
        row.get("capturable_clicks_low", s.get("capturable_clicks_low")),
        row.get("capturable_clicks_high", s.get("capturable_clicks_high")),
    )


def features(row: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(features that reduce clicks, other features present), as readable labels."""
    model = report(row).get("click_model") or {}
    costly = [f"{f['label']} ({f['position_1_effect_percent']}% at #1)" for f in model.get("factors") or []]
    neutral = [t.replace("_", " ").capitalize() for t in model.get("neutral_features") or []]
    return costly, neutral


def positions(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Page-one positions with domains; older analyses have only the click model's positions."""
    rep = report(row)
    return rep.get("page_one") or [{**p, "domain": None} for p in (rep.get("click_model") or {}).get("positions") or []]


def search_split(row: dict[str, Any]) -> tuple[float, float, float]:
    """What happens to 100 searches: (% clicking an organic result on page one, % taken by SERP features,
    % going elsewhere or not clicking). Page one without features would send the baseline share."""
    organic = float(summary(row).get("organic_ctr_total") or 0)
    plain = sum(BASELINE_CTR[: min(len(positions(row)), len(BASELINE_CTR))])
    taken = max(plain - organic, 0.0)
    return organic, taken, max(100.0 - organic - taken, 0.0)


def ranked(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dashboard order: most capturable clicks first, then keywords without volume by organic click-through."""
    def key(row):
        mid, _, _ = clicks(row)
        if mid is not None:
            return (0, -float(mid))
        return (1, -float(summary(row).get("organic_ctr_total") or 0))
    return sorted(rows, key=key)


def when(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d %b %Y")
    except ValueError:
        return iso
