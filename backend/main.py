from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from report_export import generate_csv_detailed, generate_pdf_detailed

_BACKEND_DIR = Path(__file__).resolve().parent
# Load backend/.env first, then optional cwd .env (helps if uvicorn cwd differs).
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv()


def _env_clean(value: str | None) -> str | None:
    if value is None:
        return None
    s = value.strip().replace("\ufeff", "").strip()
    return s or None


# Standard (Regular) Google Organic SERP — not Advanced.
# Docs: SERP Google Organic Live Regular — returns classic organic-style results.
DATAFORSEO_BASE_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
DATAFORSEO_KEYWORDS_DATA_URL = "https://api.dataforseo.com/v3/keywords_data/google/search_volume/live"
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Traffic Opportunity API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    keyword: str = Field(..., min_length=1)
    location_name: str = "United States"
    language_name: str = "English"
    mock_mode: bool = False


class DetailedReportRow(BaseModel):
    """Full analyze row as shown in the UI (include `report` for cards + charts in exports)."""

    keyword: str
    raw_volume: float = 0
    adjusted_volume: float = 0
    saturation_score: float = 0
    organic_results: int = 0
    total_results: int = 0
    penalty_applied: bool = False
    source: str = ""
    mock_mode: bool = False
    report: dict[str, Any] | None = None


class ReportRequest(BaseModel):
    rows: list[DetailedReportRow]
    format: Literal["csv", "pdf"] = "csv"


def _cache_key(keyword: str, location_name: str, language_name: str, mock_mode: bool) -> str:
    base = f"{keyword.strip().lower()}::{location_name.strip().lower()}::{language_name.strip().lower()}::{mock_mode}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _load_cached_response(key: str) -> dict[str, Any] | None:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_cached_response(key: str, payload: dict[str, Any]) -> None:
    path = CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_mock_payload(keyword: str, location_name: str, language_name: str) -> dict[str, Any]:
    seed = int(hashlib.md5(f"{keyword}{location_name}{language_name}".encode("utf-8")).hexdigest(), 16)
    total_items = 8 + (seed % 4)
    organic_count = 6 + (seed % 3)
    if organic_count > total_items:
        organic_count = total_items
    search_volume = 600 + (seed % 2400)

    items: list[dict[str, Any]] = []
    for i in range(total_items):
        item_type = "organic" if i < organic_count else "featured_snippet"
        items.append(
            {
                "type": item_type,
                "rank_group": i + 1,
                "domain": f"example-{i + 1}.com",
            }
        )

    return {
        "tasks": [
            {
                "result": [
                    {
                        "keyword": keyword,
                        "keyword_data": {"search_volume": search_volume},
                        "items": items,
                    }
                ]
            }
        ]
    }


def _dataforseo_credentials() -> tuple[str, str]:
    """DataForSEO Basic auth: email (login) + password from dashboard."""
    email = _env_clean(os.getenv("DATAFORSEO_EMAIL")) or _env_clean(os.getenv("DATAFORSEO_LOGIN"))
    password = _env_clean(os.getenv("DATAFORSEO_PASSWORD"))
    if not email or not password:
        env_path = _BACKEND_DIR / ".env"
        raise HTTPException(
            status_code=503,
            detail=(
                "DataForSEO is not configured. Set DATAFORSEO_EMAIL and DATAFORSEO_PASSWORD "
                f"in {env_path} (use your account email and API password from the DataForSEO dashboard). "
                "Restart the server after saving. Optional: DATAFORSEO_LOGIN can be used instead of EMAIL."
            ),
        )
    return email, password


def _raise_if_dataforseo_api_error(payload: dict[str, Any]) -> None:
    """DataForSEO returns HTTP 200 with status_code 20000 = OK; other codes mean failure."""
    root_code = payload.get("status_code")
    root_msg = str(payload.get("status_message", ""))
    if root_code is not None and root_code != 20000:
        raise HTTPException(
            status_code=502,
            detail=f"DataForSEO API error {root_code}: {root_msg or 'no message'}",
        )

    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise HTTPException(status_code=502, detail="DataForSEO returned no tasks in the response.")

    task = tasks[0]
    if not isinstance(task, dict):
        raise HTTPException(status_code=502, detail="DataForSEO returned an invalid task object.")

    task_code = task.get("status_code")
    task_msg = str(task.get("status_message", ""))
    if task_code is not None and task_code != 20000:
        raise HTTPException(
            status_code=502,
            detail=(
                f"DataForSEO task error {task_code}: {task_msg or 'no message'}. "
                "Check keyword, location_name, language_name, and account balance/access."
            ),
        )

    results = task.get("result")
    if not results or not isinstance(results, list):
        raise HTTPException(
            status_code=502,
            detail=f"DataForSEO returned no result items. Task message: {task_msg or 'none'}",
        )


def _fetch_dataforseo(keyword: str, location_name: str, language_name: str) -> dict[str, Any]:
    login, password = _dataforseo_credentials()

    post_data = [{"keyword": keyword, "location_name": location_name, "language_name": language_name}]
    try:
        res = requests.post(
            DATAFORSEO_BASE_URL,
            auth=(login, password),  # HTTP Basic: email + API password
            json=post_data,
            timeout=40,
        )
        res.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"DataForSEO HTTP request failed: {exc}") from exc

    try:
        payload: dict[str, Any] = res.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="DataForSEO returned invalid JSON.") from exc

    _raise_if_dataforseo_api_error(payload)
    return payload


def _fetch_search_volume(keyword: str, location_name: str, language_name: str) -> float:
    """Fetch search volume from DataForSEO keywords_data endpoint."""
    login, password = _dataforseo_credentials()
    
    # Keywords API expects 'keywords' as an array, not 'keyword'
    post_data = [{"keywords": [keyword], "location_name": location_name, "language_name": language_name}]
    
    try:
        print(f"[Search Volume] Fetching volume for keyword='{keyword}'")
        res = requests.post(
            DATAFORSEO_KEYWORDS_DATA_URL,
            auth=(login, password),
            json=post_data,
            timeout=20,
        )
        res.raise_for_status()
        data = res.json()
        
        print(f"[Search Volume] Full API Response: {json.dumps(data, indent=2)}")
        print(f"[Search Volume] API Response status_code: {data.get('status_code')}")
        
        if data.get("status_code") != 20000:
            print(f"[Search Volume] API Error: {data.get('status_code')} - {data.get('status_message')}")
            return 0.0
        
        tasks = data.get("tasks", [])
        if not tasks:
            print(f"[Search Volume] No tasks in response")
            return 0.0
        
        task = tasks[0]
        print(f"[Search Volume] Task keys: {task.keys()}")
        print(f"[Search Volume] Task status_code: {task.get('status_code')}")
        
        results = task.get("result", [])
        if not results:
            print(f"[Search Volume] No results in task. Full task: {json.dumps(task, indent=2)}")
            return 0.0
        
        result = results[0]
        print(f"[Search Volume] Result: {json.dumps(result, indent=2)}")
        search_volume = result.get("search_volume", 0.0)
        print(f"[Search Volume] Extracted volume: {search_volume}")
        return float(search_volume or 0.0)
        
    except Exception as e:
        print(f"[Search Volume] Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 0.0


def _first_result(payload: dict[str, Any]) -> dict[str, Any]:
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


def _build_analyze_report(
    *,
    keyword: str,
    raw_volume: float,
    adjusted_volume: float,
    organic_results: int,
    total_results: int,
    non_organic_detected: bool,
    type_breakdown: dict[str, int],
    non_organic_types: list[str],
) -> dict[str, Any]:
    """Human-readable sections + numeric summary for UI and exports."""
    saturation_score = (organic_results / total_results) if total_results else 0.0
    non_organic_count = total_results - organic_results
    penalty_pct = 30 if non_organic_detected else 0
    penalty_factor = 0.7 if non_organic_detected else 1.0
    volume_lost = round(raw_volume - adjusted_volume, 2)
    demand_per_organic = (
        round(adjusted_volume / organic_results, 2) if organic_results else None
    )

    if saturation_score >= 0.85:
        sat_label = "high organic share"
        sat_hint = "Most visible positions are standard organic listings, so competition for blue links is strong."
    elif saturation_score >= 0.5:
        sat_label = "mixed SERP"
        sat_hint = "Organic and non-organic result types mix; monitor which formats steal clicks."
    else:
        sat_label = "SERP-heavy on non-organic"
        sat_hint = "A large share of items are not classic organic results; expect fewer clicks on traditional results."

    if non_organic_detected:
        penalty_body = (
            f"At least one SERP item is not type \"organic\" (e.g. {', '.join(non_organic_types[:5])}"
            + ("…" if len(non_organic_types) > 5 else "")
            + "). The model reduces estimated monthly demand by 30%: "
            f"adjusted volume = raw volume × {penalty_factor}."
        )
    else:
        penalty_body = (
            "All analyzed items are organic listings. No clickability penalty is applied; "
            "adjusted volume equals raw search volume."
        )

    interpretation = (
        f"For “{keyword}”, monthly search volume is about {raw_volume:,.0f} (raw). "
    )
    if non_organic_detected:
        interpretation += (
            f"After a 30% penalty, “true demand” for classic organic clicks is about {adjusted_volume:,.0f}. "
        )
    else:
        interpretation += f"Estimated demand stays {adjusted_volume:,.0f} with no penalty. "
    interpretation += (
        f"Saturation is {organic_results} organic / {total_results} total = {saturation_score:.1%}. "
    )
    if demand_per_organic is not None:
        interpretation += (
            f"Roughly {demand_per_organic:,.0f} adjusted-demand units per organic slot (adjusted ÷ organic count)."
        )

    return {
        "summary": {
            "keyword": keyword,
            "raw_volume": raw_volume,
            "adjusted_volume": round(adjusted_volume, 2),
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
        },
        "sections": [
            {
                "title": "Search demand (volume)",
                "body": (
                    f"Raw monthly search volume from keyword data is {raw_volume:,.0f}. "
                    f"This is the baseline demand before SERP-shape adjustments."
                ),
            },
            {
                "title": "SERP composition & saturation",
                "body": (
                    f"The API returned {total_results} items. Of those, {organic_results} are organic "
                    f"and {non_organic_count} are not. Saturation score = organic ÷ total = "
                    f"{saturation_score:.4f} ({saturation_score:.1%}). Breakdown by type: "
                    + ", ".join(f"{k}: {v}" for k, v in sorted(type_breakdown.items(), key=lambda x: -x[1]))
                    + f". This is a {sat_label}: {sat_hint}"
                ),
            },
            {
                "title": "Clickability penalty (non-organic items)",
                "body": penalty_body,
            },
            {
                "title": "Adjusted volume (“true demand” for organic)",
                "body": (
                    f"Adjusted volume is {adjusted_volume:,.2f}. "
                    + (
                        f"That is {volume_lost:,.2f} below raw volume due to the penalty. "
                        if non_organic_detected
                        else "No reduction was applied. "
                    )
                    + (
                        f"Dividing by {organic_results} organic slots gives ~{demand_per_organic:,.2f} per slot."
                        if demand_per_organic is not None
                        else ""
                    ),
                ),
            },
            {
                "title": "How to read this report",
                "body": (
                    "Higher raw volume means more people search the term. "
                    "Higher saturation (organic share) means more of the SERP is classic rankings. "
                    "When non-organic blocks appear, adjusted volume is discounted because clicks are diverted. "
                    "Compare adjusted volume to organic slots to judge opportunity per listing."
                ),
            },
        ],
    }


def analyze_payload(payload: dict[str, Any], keyword_fallback: str) -> dict[str, Any]:
    result = _first_result(payload)
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

    keyword_data = result.get("keyword_data", {})
    raw_volume = 0.0
    if isinstance(keyword_data, dict):
        raw_volume = float(keyword_data.get("search_volume") or 0)

    adjusted_volume = raw_volume * (0.7 if non_organic_detected else 1.0)
    saturation_score = (organic_results / total_results) if total_results else 0.0
    keyword = str(result.get("keyword") or keyword_fallback)
    non_organic_types_sorted = sorted(non_organic_type_set)

    report = _build_analyze_report(
        keyword=keyword,
        raw_volume=raw_volume,
        adjusted_volume=adjusted_volume,
        organic_results=organic_results,
        total_results=total_results,
        non_organic_detected=non_organic_detected,
        type_breakdown=type_breakdown,
        non_organic_types=non_organic_types_sorted,
    )

    return {
        "keyword": keyword,
        "raw_volume": raw_volume,
        "adjusted_volume": round(adjusted_volume, 2),
        "saturation_score": round(saturation_score, 4),
        "organic_results": organic_results,
        "total_results": total_results,
        "penalty_applied": non_organic_detected,
        "report": report,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/dataforseo")
def health_dataforseo() -> dict[str, bool]:
    """Whether email + API password are loaded (does not verify balance or call the API)."""
    email = _env_clean(os.getenv("DATAFORSEO_EMAIL")) or _env_clean(os.getenv("DATAFORSEO_LOGIN"))
    password = _env_clean(os.getenv("DATAFORSEO_PASSWORD"))
    return {"credentials_loaded": bool(email and password)}



@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    key = _cache_key(request.keyword, request.location_name, request.language_name, request.mock_mode)
    cached = _load_cached_response(key)
    
    if cached is not None:
        analysis = analyze_payload(cached, request.keyword)
        return {"source": "cache", "mock_mode": request.mock_mode, **analysis}

    if request.mock_mode:
        payload = _build_mock_payload(request.keyword, request.location_name, request.language_name)
    else:
        # 1. Fetch SERP structure (organic vs non-organic breakdown)
        payload = _fetch_dataforseo(request.keyword, request.location_name, request.language_name)
        
        # 2. Fetch search volume separately
        volume = _fetch_search_volume(request.keyword, request.location_name, request.language_name)
        
        # 3. Inject volume into the payload so analyze_payload can use it
        if payload.get("tasks") and payload["tasks"][0].get("result"):
            payload["tasks"][0]["result"][0]["keyword_data"] = {"search_volume": volume}

    _save_cached_response(key, payload)
    analysis = analyze_payload(payload, request.keyword)
    return {"source": "api", "mock_mode": request.mock_mode, **analysis}


@app.post("/report")
def report(request: ReportRequest) -> Response:
    rows_payload = [r.model_dump() for r in request.rows]
    if request.format == "csv":
        content = generate_csv_detailed(rows_payload)
        headers = {"Content-Disposition": "attachment; filename=traffic-opportunity-report.csv"}
        return Response(content=content, media_type="text/csv", headers=headers)

    content = generate_pdf_detailed(rows_payload)
    headers = {"Content-Disposition": "attachment; filename=traffic-opportunity-report.pdf"}
    return Response(content=content, media_type="application/pdf", headers=headers)
