"""Turns a SERP snapshot into Startly's capturable-clicks report (model: ctr_model.py)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ctr_config import BASELINE_CTR
from ctr_model import estimate_clicks
from insights import page_one, recommendations, verdict

# Features that answer the query on the page itself, so the report warns about zero-click risk.
ZERO_CLICK_FEATURES = {"ai_overview", "local_pack"}
COMMERCIAL_TYPES = {"paid", "google_ads", "shopping"}
# Clicks across the top 3 positions above which a keyword is called worth targeting.
TOP3_CLICKS_WORTH_TARGETING = 500


def first_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept a normalized snapshot ({keyword, keyword_data, items}) or a raw DataForSEO payload."""
    if "items" in payload and "tasks" not in payload:
        return payload
    tasks = payload.get("tasks", [])
    if not tasks or not isinstance(tasks, list):
        raise HTTPException(status_code=502, detail="Unexpected response: tasks is empty.")
    task = tasks[0]
    results = task.get("result", []) if isinstance(task, dict) else []
    if not results or not isinstance(results, list):
        raise HTTPException(status_code=502, detail="Unexpected response: result is empty.")
    result = results[0]
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="Unexpected response: invalid result shape.")
    return result


def click_loss_percent(organic_results: int, model: dict[str, Any]) -> int:
    """Share of organic clicks SERP features remove, versus a clean page with the same organic count."""
    clean = sum(BASELINE_CTR[: min(organic_results, len(BASELINE_CTR))])
    if clean <= 0:
        return 0
    return max(0, round((1 - model["organic_ctr_total"] / clean) * 100))


def _fmt_range(mid: float | None, low: float | None, high: float | None, unit: str) -> str:
    if mid is None:
        return "unknown"
    if low == high:
        return f"{mid:,.0f} {unit}"
    return f"{mid:,.0f} {unit} (range {low:,.0f}–{high:,.0f})"


def build_analyze_report(
    *,
    keyword: str,
    raw_volume: float,
    has_volume: bool,
    organic_results: int,
    total_results: int,
    type_breakdown: dict[str, int],
    non_organic_types: list[str],
    model: dict[str, Any],
) -> dict[str, Any]:
    """Human-readable sections + numeric summary for UI and exports."""
    saturation_score = (organic_results / total_results) if total_results else 0.0
    non_organic_count = total_results - organic_results
    loss_pct = click_loss_percent(organic_results, model)
    clicks = model["capturable_clicks"]
    clicks_low, clicks_high = model["capturable_clicks_low"], model["capturable_clicks_high"]
    positions = model["positions"]
    factors = {f["feature"]: f for f in model["factors"]}
    demand_per_organic = round(clicks / organic_results, 2) if clicks is not None and organic_results else None

    # Dynamic Labels & Sentiment
    if saturation_score >= 0.8:
        sat_label = "Organic Dominant"
        sat_status = "success"
        sat_desc = "High visibility for standard organic listings."
    elif saturation_score >= 0.5:
        sat_label = "Balanced SERP"
        sat_status = "warning"
        sat_desc = "Mix of organic and rich SERP elements."
    else:
        sat_label = "Saturated / Non-Organic"
        sat_status = "danger"
        sat_desc = "SERP is heavily dominated by special features."

    ctr_text = f"{model['organic_ctr_total']:.1f}% of searches"
    if has_volume:
        demand_body = (
            f"Of {raw_volume:,.0f} monthly searches, about "
            f"{_fmt_range(clicks, clicks_low, clicks_high, 'clicks')} are expected to reach an organic result on page one "
            f"({ctr_text}). SERP features remove about {loss_pct}% of the clicks a plain results page would send."
        )
    else:
        demand_body = (
            f"Page one sends organic clicks on about {ctr_text}. SERP features remove about {loss_pct}% of the clicks "
            "a plain results page would send. Enter a monthly search volume to turn this into click counts."
        )

    costly = [f["label"] for f in model["factors"]]
    neutral = [t.replace("_", " ") for t in model["neutral_features"]]
    real_estate = f"Classic organic links hold {saturation_score:.1%} of SERP items. "
    if costly:
        real_estate += f"{', '.join(costly)} reduce organic clicks."
    else:
        real_estate += "No features that measurably reduce organic clicks were found."
    if neutral:
        real_estate += f" {', '.join(neutral).capitalize()} appear but don't measurably lower organic clicks."

    sections = [
        {"title": "Effective Market Demand", "body": demand_body},
        {"title": "SERP Real Estate Allocation", "body": real_estate},
    ]

    if positions:
        picks = [p for p in positions if p["position"] in (1, 2, 3)] + ([positions[-1]] if len(positions) > 3 else [])
        if has_volume:
            parts = [f"#{p['position']} ~ {p['clicks']:,} clicks" for p in picks]
            body = "Estimated monthly clicks by ranking: " + ", ".join(parts) + "."
        else:
            parts = [f"#{p['position']} ~ {p['ctr']:.1f}%" for p in picks]
            body = "Estimated share of searches clicking each ranking: " + ", ".join(parts) + "."
        sections.append({"title": "Value by Position", "body": body})

    zero_click = [factors[f] for f in ("ai_overview", "local_pack") if f in factors]
    if zero_click:
        effects = "; ".join(f"{f['label']} {f['position_1_effect_percent']}% at #1" for f in zero_click)
        sections.append({
            "title": "Zero-Click Search Risk",
            "body": (
                f"Google answers part of this query on the page itself ({effects}). Many searchers won't click any "
                "result. Aim to be cited in the answer, or target the high-intent queries around it."
            ),
        })

    if set(non_organic_types) & COMMERCIAL_TYPES:
        sections.append({
            "title": "Competitive Commercial Intent",
            "body": "Ads or shopping results are present: advertisers pay for this traffic, which signals the keyword has commercial value, while top ads take some clicks from position 1.",
        })

    if model["low_confidence_factors"]:
        sections.append({
            "title": "Model Confidence",
            "body": (
                f"This estimate includes {', '.join(model['low_confidence_factors'])}, which relies on older data. "
                "Treat the range as approximate."
            ),
        })

    top3 = [p for p in positions if p["position"] <= 3]
    if not positions:
        verdict_body = "No classic organic listings were found on page one, so there is no organic slot to target."
    elif not has_volume:
        verdict_body = "Add a monthly search volume to see whether the top positions are worth the effort."
    else:
        top3_clicks = sum(p["clicks"] for p in top3)
        verdict_body = (
            f"The top {len(top3)} positions are worth about {top3_clicks:,} clicks a month combined, so "
            + ("this is worth targeting if you can reach the top three."
               if top3_clicks >= TOP3_CLICKS_WORTH_TARGETING
               else "even a top ranking brings modest traffic; target it only if those visitors are high value.")
        )
    sections.append({"title": "Listing Scalability Verdict", "body": verdict_body})

    adjusted = float(clicks) if clicks is not None else 0.0
    return {
        "summary": {
            "keyword": keyword,
            "raw_volume": raw_volume,
            "adjusted_volume": adjusted,
            "capturable_clicks": clicks,
            "capturable_clicks_low": clicks_low,
            "capturable_clicks_high": clicks_high,
            "organic_ctr_total": model["organic_ctr_total"],
            "saturation_score": round(saturation_score, 4),
            "saturation_percent": round(saturation_score * 100, 2),
            "organic_results": organic_results,
            "non_organic_count": non_organic_count,
            "total_results": total_results,
            "penalty_applied": loss_pct > 0,
            "penalty_percent": loss_pct,
            "penalty_factor": round(1 - loss_pct / 100, 2),
            "volume_reduction": round(raw_volume - adjusted, 2) if has_volume else 0,
            "type_breakdown": type_breakdown,
            "non_organic_types": non_organic_types,
            "demand_per_organic_slot": demand_per_organic,
            "saturation_label": sat_label,
            "saturation_status": sat_status,
            "saturation_desc": sat_desc,
        },
        "sections": sections,
        "click_model": model,
    }


def analyze_payload(
    payload: dict[str, Any],
    keyword_fallback: str,
    volume_override: float | None = None,
    volume_source: str = "user",
) -> dict[str, Any]:
    """Score a snapshot. `volume_override` (labelled `volume_source`) wins over volume stored in the payload."""
    result = first_result(payload)
    items = result.get("items", [])
    if not isinstance(items, list):
        items = []

    total_results = len(items)
    organic_results = sum(1 for item in items if isinstance(item, dict) and item.get("type") == "organic")

    type_breakdown: dict[str, int] = {}
    non_organic_type_set: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        t = item.get("type")
        key = str(t) if t is not None else "unknown"
        type_breakdown[key] = type_breakdown.get(key, 0) + 1
        if t and t != "organic":
            non_organic_type_set.add(str(t))

    if volume_override is not None:
        raw_volume = float(volume_override)
    else:
        keyword_data = result.get("keyword_data") or {}
        stored = keyword_data.get("search_volume") if isinstance(keyword_data, dict) else None
        raw_volume = float(stored or 0)
        volume_source = str(keyword_data.get("source") or "api") if stored is not None else "unknown"
    has_volume = volume_source != "unknown"

    non_organic_types = sorted(non_organic_type_set)
    model = estimate_clicks(raw_volume if has_volume else None, organic_results, non_organic_types)
    saturation_score = (organic_results / total_results) if total_results else 0.0
    keyword = str(result.get("keyword") or keyword_fallback)

    report = build_analyze_report(
        keyword=keyword,
        raw_volume=raw_volume,
        has_volume=has_volume,
        organic_results=organic_results,
        total_results=total_results,
        type_breakdown=type_breakdown,
        non_organic_types=non_organic_types,
        model=model,
    )
    summary = report["summary"]
    report["verdict"] = verdict(model, has_volume, summary["penalty_percent"])
    report["recommendations"] = recommendations(
        model=model, types=set(non_organic_types), has_volume=has_volume,
        loss_pct=summary["penalty_percent"], verdict_tone=report["verdict"]["tone"],
    )
    report["page_one"] = page_one(items, model["positions"])

    return {
        "keyword": keyword,
        "raw_volume": raw_volume,
        "volume_source": volume_source,
        "adjusted_volume": summary["adjusted_volume"],
        "capturable_clicks": model["capturable_clicks"],
        "capturable_clicks_low": model["capturable_clicks_low"],
        "capturable_clicks_high": model["capturable_clicks_high"],
        "saturation_score": round(saturation_score, 4),
        "organic_results": organic_results,
        "total_results": total_results,
        "penalty_applied": summary["penalty_applied"],
        "report": report,
    }
