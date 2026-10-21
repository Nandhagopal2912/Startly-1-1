"""Turns a SERP snapshot into Startly's adjusted-demand report."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

ZERO_CLICK_TYPES = {"answer_box", "ai_overview", "knowledge_graph"}
# "paid" is the item type DataForSEO and the Serper adapter use for Google Ads.
COMMERCIAL_TYPES = {"paid", "google_ads", "shopping"}


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


def penalty_percent(non_organic_types: list[str]) -> int:
    if not non_organic_types:
        return 0
    types = set(non_organic_types)
    if types & ZERO_CLICK_TYPES:
        return 45  # Massive zero-click diversion
    if types & COMMERCIAL_TYPES:
        return 35  # Significant commercial diversion
    return 20  # Standard informational noise


def build_analyze_report(
    *,
    keyword: str,
    raw_volume: float,
    organic_results: int,
    total_results: int,
    non_organic_detected: bool,
    type_breakdown: dict[str, int],
    non_organic_types: list[str],
) -> dict[str, Any]:
    """Human-readable sections + numeric summary for UI and exports."""
    saturation_score = (organic_results / total_results) if total_results else 0.0
    non_organic_count = total_results - organic_results

    penalty_pct = penalty_percent(non_organic_types)
    penalty_factor = (100 - penalty_pct) / 100
    adj_volume = raw_volume * penalty_factor
    volume_lost = round(raw_volume - adj_volume, 2)
    demand_per_organic = (
        round(adj_volume / organic_results, 2) if organic_results else None
    )

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

    sections = [
        {
            "title": "Effective Market Demand",
            "body": (
                f"The initial keyword demand of {raw_volume:,.0f} searches is filtered down to an "
                f"effective volume of {adj_volume:,.0f} due to a {penalty_pct}% SERP visibility penalty."
            ),
        },
        {
            "title": "SERP Real Estate Allocation",
            "body": (
                f"Classic organic links hold {saturation_score:.1%} of available SERP slots. "
                + (f"Invocations of {', '.join(non_organic_types[:3])} compete aggressively for attention."
                   if non_organic_types else "This is a rare 'Blue Link' pure organic environment.")
            ),
        }
    ]

    # Pattern Injection Logic
    if any(t in ["ai_overview", "answer_box"] for t in non_organic_types):
        sections.append({
            "title": "Zero-Click Search Risk",
            "body": "Critical: Google's direct-answer modules are active. Most users will satisfy their query without clicking through to a website. Focus on deep-topic authority or high-intent conversion."
        })

    if set(non_organic_types) & {"paid", "google_ads"}:
        sections.append({
            "title": "Competitive Commercial Intent",
            "body": "High-intent transactional indicators detected. While paid ads reduce organic CTR, they validate that this keyword has significant monetary value."
        })

    if demand_per_organic is None:
        verdict_body = "No classic organic listings were found on page one, so there is no organic slot to target."
    else:
        verdict_body = (
            f"With {demand_per_organic:,.0f} adjusted search units available per organic ranking slot, "
            + ("this represents a highly scalable SEO target." if demand_per_organic > 400
               else "this keyword requires precision targeting to be profitable.")
        )
    sections.append({"title": "Listing Scalability Verdict", "body": verdict_body})

    return {
        "summary": {
            "keyword": keyword,
            "raw_volume": raw_volume,
            "adjusted_volume": round(adj_volume, 2),
            "saturation_score": round(saturation_score, 4),
            "saturation_percent": round(saturation_score * 100, 2),
            "organic_results": organic_results,
            "non_organic_count": non_organic_count,
            "total_results": total_results,
            "penalty_applied": non_organic_detected,
            "penalty_percent": penalty_pct,
            "penalty_factor": penalty_factor,
            "volume_reduction": volume_lost,
            "type_breakdown": type_breakdown,
            "non_organic_types": non_organic_types,
            "demand_per_organic_slot": demand_per_organic,
            "saturation_label": sat_label,
            "saturation_status": sat_status,
            "saturation_desc": sat_desc
        },
        "sections": sections,
    }


def analyze_payload(
    payload: dict[str, Any], keyword_fallback: str, volume_override: float | None = None
) -> dict[str, Any]:
    result = first_result(payload)
    items = result.get("items", [])
    if not isinstance(items, list):
        items = []

    total_results = len(items)
    organic_results = sum(1 for item in items if isinstance(item, dict) and item.get("type") == "organic")
    non_organic_detected = any(
        isinstance(item, dict) and item.get("type") and item.get("type") != "organic" for item in items
    )

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
        volume_source = "user"
    else:
        keyword_data = result.get("keyword_data") or {}
        stored = keyword_data.get("search_volume") if isinstance(keyword_data, dict) else None
        raw_volume = float(stored or 0)
        volume_source = str(keyword_data.get("source") or "api") if stored is not None else "unknown"

    saturation_score = (organic_results / total_results) if total_results else 0.0
    keyword = str(result.get("keyword") or keyword_fallback)

    report = build_analyze_report(
        keyword=keyword,
        raw_volume=raw_volume,
        organic_results=organic_results,
        total_results=total_results,
        non_organic_detected=non_organic_detected,
        type_breakdown=type_breakdown,
        non_organic_types=sorted(non_organic_type_set),
    )

    return {
        "keyword": keyword,
        "raw_volume": raw_volume,
        "volume_source": volume_source,
        "adjusted_volume": report["summary"]["adjusted_volume"],
        "saturation_score": round(saturation_score, 4),
        "organic_results": organic_results,
        "total_results": total_results,
        "penalty_applied": non_organic_detected,
        "report": report,
    }
