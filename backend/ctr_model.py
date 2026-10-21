"""Estimate organic clicks per position from a SERP's features (see ctr_config.py for the data).

Overlapping features make the true effect uncertain, so the model returns a range:
- low: every present feature's multiplier stacks (effects are independent)
- high: only the strongest multiplier applies at each position (effects fully overlap)
- estimate: the midpoint of the two
"""

from __future__ import annotations

import math
from typing import Any, Iterable

from ctr_config import BASELINE_CTR, BASELINE_SOURCE, FEATURE_ALIASES, FEATURES, NEUTRAL_FEATURES


def _canonical(feature_types: Iterable[str]) -> set[str]:
    return {FEATURE_ALIASES.get(t, t) for t in feature_types}


def _multiplier(feature: str, index: int) -> float:
    values = FEATURES[feature]["multipliers"]
    return values[index] if index < len(values) else 1.0


def _non_increasing(curve: list[float]) -> list[float]:
    """A lower position never gets more clicks than the one above it (smooths noise in source data)."""
    out: list[float] = []
    for value in curve:
        out.append(min(value, out[-1]) if out else value)
    return out


def ctr_curves(organic_count: int, feature_types: Iterable[str]) -> tuple[list[float], list[float]]:
    """(low, high) CTR percentages for organic positions 1..organic_count (max 10)."""
    present = [f for f in _canonical(feature_types) if f in FEATURES]
    low, high = [], []
    for i in range(min(max(organic_count, 0), len(BASELINE_CTR))):
        mults = [_multiplier(f, i) for f in present]
        low.append(BASELINE_CTR[i] * math.prod(mults))
        high.append(BASELINE_CTR[i] * min(mults, default=1.0))
    return _non_increasing(low), _non_increasing(high)


def estimate_clicks(volume: float | None, organic_count: int, feature_types: Iterable[str]) -> dict[str, Any]:
    """Click estimate for a SERP. With no volume, CTRs are returned and click counts are None."""
    types = _canonical(feature_types)
    low, high = ctr_curves(organic_count, types)

    def clicks(pct: float) -> float | None:
        return round(volume * pct / 100) if volume is not None else None

    positions = []
    for i, (lo, hi) in enumerate(zip(low, high)):
        mid = (lo + hi) / 2
        positions.append({
            "position": i + 1,
            "ctr": round(mid, 3),
            "ctr_low": round(lo, 3),
            "ctr_high": round(hi, 3),
            "clicks": clicks(mid),
            "clicks_low": clicks(lo),
            "clicks_high": clicks(hi),
        })

    total_low, total_high = sum(low), sum(high)
    total_mid = (total_low + total_high) / 2
    factors = [
        {
            "feature": f,
            "label": FEATURES[f]["label"],
            "position_1_effect_percent": round((FEATURES[f]["multipliers"][0] - 1) * 100),
            "confidence": FEATURES[f]["confidence"],
            "source": FEATURES[f]["source"],
            "url": FEATURES[f]["url"],
        }
        for f in sorted(types)
        if f in FEATURES
    ]
    return {
        "organic_ctr_total": round(total_mid, 2),
        "organic_ctr_total_low": round(total_low, 2),
        "organic_ctr_total_high": round(total_high, 2),
        "capturable_clicks": clicks(total_mid),
        "capturable_clicks_low": clicks(total_low),
        "capturable_clicks_high": clicks(total_high),
        "positions": positions,
        "factors": factors,
        "neutral_features": sorted(t for t in types if t in NEUTRAL_FEATURES),
        "low_confidence_factors": [f["label"] for f in factors if f["confidence"] == "low"],
        "baseline_source": BASELINE_SOURCE,
    }
