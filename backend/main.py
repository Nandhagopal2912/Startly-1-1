from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

import config
from cache import cache_key, load_cached_response, save_cached_response
from providers import get_serp_provider, get_volume_provider
from providers.dataforseo import credentials as dataforseo_credentials
from report_export import generate_csv_detailed, generate_pdf_detailed
from scoring import analyze_payload
from usage import calls_today

log = logging.getLogger(__name__)

app = FastAPI(title="Traffic Opportunity API", version="1.1.0")
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


def _fetch_snapshot(request: AnalyzeRequest) -> dict[str, Any]:
    provider = get_serp_provider("mock" if request.mock_mode else None)
    snapshot = provider.fetch_serp(request.keyword, request.location_name, request.language_name)

    # Skip the paid volume call when the user supplied a number or the provider already had one.
    if request.mock_mode or request.search_volume is not None or snapshot["keyword_data"]:
        return snapshot

    volume_provider = get_volume_provider()
    if volume_provider is None or not volume_provider.is_configured():
        return snapshot
    try:
        volume = volume_provider.fetch_volume(request.keyword, request.location_name, request.language_name)
    except HTTPException as exc:
        # The SERP is still useful without volume; don't throw away a paid call.
        log.warning("Volume lookup failed for %r: %s", request.keyword, exc.detail)
        return snapshot
    if volume is not None:
        snapshot["keyword_data"] = {"search_volume": volume, "source": volume_provider.name}
    return snapshot


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
    key = cache_key(request.keyword, request.location_name, request.language_name, request.mock_mode)
    payload = load_cached_response(key)
    source = "cache"
    if payload is None:
        payload = _fetch_snapshot(request)
        save_cached_response(key, payload)
        source = "api"

    analysis = analyze_payload(payload, request.keyword, volume_override=request.search_volume)
    return {
        "source": source,
        "mock_mode": request.mock_mode,
        "provider": payload.get("provider", "dataforseo"),
        **analysis,
    }


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
