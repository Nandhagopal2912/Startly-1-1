"""Bulk analysis: preview the API cost of a keyword list, then analyze and rank it by capturable clicks."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

import config
import store
from analysis import AnalyzeRequest, run_analysis
from db import norm
from usage import calls_today

log = logging.getLogger(__name__)

BULK_MAX_KEYWORDS = 50
# Parallel analyses per bulk run; keeps a 50-keyword run to about a minute without hammering the provider.
BULK_WORKERS = 4


class BulkKeyword(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    search_volume: float | None = Field(default=None, ge=0)


class BulkRequest(BaseModel):
    keywords: list[BulkKeyword] = Field(..., min_length=1, max_length=BULK_MAX_KEYWORDS)
    location_name: str = "United States"
    language_name: str = "English"
    mock_mode: bool = False


def _dedupe(request: BulkRequest) -> tuple[list[BulkKeyword], int]:
    """Unique keywords in input order; a later line's volume fills in or replaces an earlier one."""
    by_key: dict[str, BulkKeyword] = {}
    for item in request.keywords:
        keyword = item.keyword.strip()
        if not keyword:
            continue
        key = norm(keyword)
        if key in by_key:
            if item.search_volume is not None:
                by_key[key] = BulkKeyword(keyword=by_key[key].keyword, search_volume=item.search_volume)
        else:
            by_key[key] = BulkKeyword(keyword=keyword, search_volume=item.search_volume)
    unique = list(by_key.values())
    return unique, len(request.keywords) - len(unique)


def bulk_preview(request: BulkRequest) -> dict[str, Any]:
    items, duplicates = _dedupe(request)
    loc, lang = request.location_name, request.language_name
    rows = []
    for item in items:
        cached = store.latest_snapshot(item.keyword, loc, lang, request.mock_mode) is not None
        has_volume = item.search_volume is not None or store.get_volume(item.keyword, loc, lang) is not None
        rows.append({"keyword": item.keyword, "cached": cached or request.mock_mode, "has_volume": has_volume})

    new_calls = sum(1 for r in rows if not r["cached"])
    used, cap = calls_today(), config.daily_api_cap()
    remaining = max(cap - used, 0)
    return {
        "items": rows,
        "total": len(rows),
        "cached": len(rows) - new_calls,
        "new_calls": new_calls,
        "without_volume": sum(1 for r in rows if not r["has_volume"]),
        "duplicates_removed": duplicates,
        "calls_today": used,
        "daily_cap": cap,
        "remaining_calls": remaining,
        "fits_in_cap": new_calls <= remaining,
    }


def _analyze_one(item: BulkKeyword, request: BulkRequest) -> dict[str, Any]:
    try:
        analysis = run_analysis(AnalyzeRequest(
            keyword=item.keyword,
            location_name=request.location_name,
            language_name=request.language_name,
            mock_mode=request.mock_mode,
            search_volume=item.search_volume,
        ))
        return {"keyword": item.keyword, "status": "ok", "analysis": analysis}
    except HTTPException as exc:
        return {"keyword": item.keyword, "status": "error", "error": str(exc.detail), "error_code": exc.status_code}
    except Exception:  # one bad keyword shouldn't sink the batch
        log.exception("Bulk analysis failed for %r", item.keyword)
        return {"keyword": item.keyword, "status": "error", "error": "Unexpected error analyzing this keyword.", "error_code": 500}


def _rank_key(result: dict[str, Any]) -> tuple[int, float]:
    """Known clicks first (most clicks first), then unknown volume by organic CTR, then errors."""
    if result["status"] != "ok":
        return (2, 0.0)
    analysis = result["analysis"]
    if analysis.get("capturable_clicks") is not None:
        return (0, -float(analysis["capturable_clicks"]))
    return (1, -float(analysis["report"]["summary"].get("organic_ctr_total") or 0))


def bulk_analyze(request: BulkRequest) -> dict[str, Any]:
    items, duplicates = _dedupe(request)
    before = calls_today()
    with ThreadPoolExecutor(max_workers=BULK_WORKERS) as pool:
        results = list(pool.map(lambda item: _analyze_one(item, request), items))

    results.sort(key=_rank_key)
    for rank, result in enumerate(results, start=1):
        result["rank"] = rank if result["status"] == "ok" else None

    errors = [r for r in results if r["status"] != "ok"]
    return {
        "results": results,
        "analyzed": len(results) - len(errors),
        "errors": len(errors),
        "cap_reached": any(r.get("error_code") == 429 for r in errors),
        "duplicates_removed": duplicates,
        "api_calls_used": calls_today() - before,
    }
