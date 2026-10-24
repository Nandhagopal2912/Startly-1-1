from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

import config
import store
from analysis import AnalyzeRequest, run_analysis
from bulk import BulkRequest, bulk_analyze, bulk_preview, dedupe_keywords
from db import init_db
from history import get_full_analysis, latest_full_analyses
from migrate_cache import import_json_cache
from ratelimit import RateLimitMiddleware
from providers import get_serp_provider, get_volume_provider
from providers.dataforseo import credentials as dataforseo_credentials
from providers.serpapi import account_info
from report_export import generate_csv_detailed, generate_pdf_detailed
from stateless import KEY_HEADER, RescoreRequest, analyze_with_own_key, clean_key, rescore
from usage import calls_today


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    import_json_cache()
    yield


app = FastAPI(title="Traffic Opportunity API", version="1.4.0", lifespan=lifespan)
# Starlette runs the last-added middleware first, so CORS wraps the rate limiter and 429s stay readable.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", KEY_HEADER],
)

MAX_REPORT_ROWS = 200


class DetailedReportRow(BaseModel):
    """Full analyze row as shown in the UI (include `report` for cards + charts in exports)."""

    keyword: str
    raw_volume: float = 0
    volume_source: str = ""
    adjusted_volume: float = 0
    saturation_score: float = 0
    organic_results: int = 0
    total_results: int = 0
    penalty_applied: bool = False
    source: str = ""
    mock_mode: bool = False
    report: dict[str, Any] | None = None


class ReportRequest(BaseModel):
    rows: list[DetailedReportRow] = Field(..., max_length=MAX_REPORT_ROWS)
    format: Literal["csv", "pdf"] = "csv"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/provider")
def health_provider() -> dict[str, Any]:
    """Active data sources and today's paid-call usage (makes no API calls)."""
    serp = get_serp_provider()
    volume = get_volume_provider()
    return {
        "serp_provider": serp.name,
        "serp_configured": serp.is_configured(),
        "volume_provider": volume.name if volume else "none",
        "volume_configured": bool(volume and volume.is_configured()),
        "calls_today": calls_today(),
        "daily_cap": config.daily_api_cap(),
        "demo_mode": config.demo_mode(),
    }


@app.get("/demo/keywords")
def demo_keywords() -> list[dict[str, Any]]:
    """Keywords the public demo can show (only available when DEMO_MODE is on)."""
    if not config.demo_mode():
        raise HTTPException(status_code=404, detail="Not found")
    return store.saved_keywords()


@app.get("/health/dataforseo")
def health_dataforseo() -> dict[str, bool]:
    """Whether email + API password are loaded (does not verify balance or call the API)."""
    return {"credentials_loaded": dataforseo_credentials() is not None}


@app.post("/analyze")
def analyze(request: AnalyzeRequest, own_key: str | None = Header(None, alias=KEY_HEADER)) -> dict[str, Any]:
    """Analyze a keyword. With an X-SerpApi-Key header the search runs on that key and nothing is stored."""
    key = clean_key(own_key)
    if key:
        return analyze_with_own_key(
            key, keyword=request.keyword, location_name=request.location_name,
            language_name=request.language_name, search_volume=request.search_volume, previous=request.previous,
        )
    return run_analysis(request)


@app.post("/rescore")
def rescore_endpoint(request: RescoreRequest) -> dict[str, Any]:
    """Re-score a results page the browser already has (e.g. after editing volume). No search, nothing stored."""
    return rescore(request)


@app.post("/key/check")
def key_check(own_key: str | None = Header(None, alias=KEY_HEADER)) -> dict[str, Any]:
    """Validate a visitor's SerpApi key and show its plan and searches left. Free: SerpApi doesn't count it."""
    key = clean_key(own_key)
    if not key:
        raise HTTPException(status_code=400, detail=f"Send your SerpApi key in the {KEY_HEADER} header.")
    return {"valid": True, **account_info(key)}


@app.post("/bulk/preview")
def bulk_preview_endpoint(request: BulkRequest, own_key: str | None = Header(None, alias=KEY_HEADER)) -> dict[str, Any]:
    """What a bulk run would cost: cached keywords are free, the rest each need one API call."""
    if clean_key(own_key):
        # The browser knows which keywords it already has; everything sent here is a search on the visitor's key.
        items, duplicates = dedupe_keywords(request)
        return {"own_key": True, "total": len(items), "new_calls": len(items), "duplicates_removed": duplicates}
    return bulk_preview(request)


@app.post("/bulk/analyze")
def bulk_analyze_endpoint(request: BulkRequest, own_key: str | None = Header(None, alias=KEY_HEADER)) -> dict[str, Any]:
    """Analyze many keywords and rank them by capturable clicks."""
    return bulk_analyze(request, own_key=clean_key(own_key))


@app.get("/history")
def history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=200),
) -> list[dict[str, Any]]:
    """Analysis summaries, newest first; `q` filters by keyword."""
    return store.recent_analyses(limit, offset, q)


@app.get("/history/latest")
def history_latest(
    limit: int = Query(20, ge=1, le=100),
    after_id: int = Query(0, ge=0, description="Only analyses with a higher id (e.g. after the dashboard was cleared)"),
) -> list[dict[str, Any]]:
    """Full results for the newest analysis of each recent keyword (restores the dashboard; no API calls)."""
    return latest_full_analyses(limit, after_id)


@app.get("/history/{analysis_id}")
def history_item(analysis_id: int) -> dict[str, Any]:
    """One saved analysis, exactly as it was shown."""
    result = get_full_analysis(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No saved analysis with id {analysis_id}.")
    return result


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
