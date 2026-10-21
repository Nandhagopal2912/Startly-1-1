from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

import config
import store
from db import init_db
from migrate_cache import import_json_cache
from providers import get_serp_provider, get_volume_provider
from providers.dataforseo import credentials as dataforseo_credentials
from report_export import generate_csv_detailed, generate_pdf_detailed
from scoring import analyze_payload
from usage import calls_today

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    import_json_cache()
    yield


app = FastAPI(title="Traffic Opportunity API", version="1.2.0", lifespan=lifespan)
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
    # Monthly searches the user already knows (e.g. from Keyword Planner); overrides any API volume.
    search_volume: float | None = Field(default=None, ge=0)


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
    rows: list[DetailedReportRow]
    format: Literal["csv", "pdf"] = "csv"


def _resolve_volume(request: AnalyzeRequest, snapshot: dict[str, Any]) -> tuple[float | None, str]:
    """Volume and its source; (None, "") means use whatever the snapshot itself carries."""
    kw, loc, lang = request.keyword, request.location_name, request.language_name
    if request.search_volume is not None:
        # Remember it, so the next analysis of this keyword doesn't need it typed again.
        store.save_volume(kw, loc, lang, request.search_volume, "user")
        return request.search_volume, "user"

    stored = store.get_volume(kw, loc, lang)
    if stored is not None:
        return stored

    # Mock snapshots and pre-SQLite cache imports carry their own volume.
    if request.mock_mode or (snapshot.get("keyword_data") or {}).get("search_volume") is not None:
        return None, ""

    volume_provider = get_volume_provider()
    if volume_provider is None or not volume_provider.is_configured():
        return None, ""
    try:
        volume = volume_provider.fetch_volume(kw, loc, lang)
    except HTTPException as exc:
        # The SERP is still useful without volume; don't throw away a paid call.
        log.warning("Volume lookup failed for %r: %s", kw, exc.detail)
        return None, ""
    if volume is None:
        return None, ""
    store.save_volume(kw, loc, lang, volume, volume_provider.name)
    return volume, volume_provider.name


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
    }


@app.get("/health/dataforseo")
def health_dataforseo() -> dict[str, bool]:
    """Whether email + API password are loaded (does not verify balance or call the API)."""
    return {"credentials_loaded": dataforseo_credentials() is not None}


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    kw, loc, lang = request.keyword, request.location_name, request.language_name
    found = store.latest_snapshot(kw, loc, lang, request.mock_mode)
    if found is not None:
        snapshot_id, payload = found
        source = "cache"
    else:
        provider = get_serp_provider("mock" if request.mock_mode else None)
        payload = provider.fetch_serp(kw, loc, lang)
        snapshot_id = store.save_snapshot(kw, loc, lang, request.mock_mode, payload)
        source = "api"

    volume, volume_source = _resolve_volume(request, payload)
    analysis = analyze_payload(payload, kw, volume_override=volume, volume_source=volume_source)
    provider_name = str(payload.get("provider") or "dataforseo")
    store.record_analysis(
        keyword=analysis["keyword"], location=loc, language=lang,
        snapshot_id=snapshot_id, provider=provider_name, analysis=analysis,
    )
    return {"source": source, "mock_mode": request.mock_mode, "provider": provider_name, **analysis}


@app.get("/history")
def history(limit: int = Query(50, ge=1, le=500)) -> list[dict[str, Any]]:
    """Most recent analyses, newest first."""
    return store.recent_analyses(limit)


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
