"""One keyword analysis end to end: snapshot (cache or provider) + volume + scoring + history."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

import store
from providers import get_serp_provider, get_volume_provider
from scoring import analyze_payload

log = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    keyword: str = Field(..., min_length=1)
    location_name: str = "United States"
    language_name: str = "English"
    mock_mode: bool = False
    # Monthly searches the user already knows (e.g. from Keyword Planner); overrides any API volume.
    search_volume: float | None = Field(default=None, ge=0)


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


def run_analysis(request: AnalyzeRequest) -> dict[str, Any]:
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
