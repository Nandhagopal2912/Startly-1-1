"""Stateless analyses for visitors who bring their own SerpApi key.

Nothing here touches the database or the server's API quota. The visitor's browser keeps the results
page ("snapshot") and sends it back to re-score it (e.g. after a volume edit) or to compare a re-check
with the previous one.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from changes import diff_snapshots
from db import utc_now
from providers.serpapi import SerpApiProvider
from scoring import analyze_payload

KEY_HEADER = "X-SerpApi-Key"
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9]{20,128}$")


class SnapshotItem(BaseModel):
    type: str = Field(..., max_length=50)
    rank_group: int | None = None
    domain: str | None = Field(None, max_length=253)


class Snapshot(BaseModel):
    """A results page as returned in `snapshot`, sent back by the browser. Limited so it can't be abused."""

    keyword: str = Field("", max_length=200)
    provider: str = Field("serpapi", max_length=30)
    items: list[SnapshotItem] = Field(default_factory=list, max_length=100)

    def payload(self) -> dict[str, Any]:
        return {"keyword": self.keyword, "provider": self.provider, "keyword_data": {}, "items": [i.model_dump() for i in self.items]}


class PreviousCheck(BaseModel):
    snapshot: Snapshot
    fetched_at: str = Field(..., max_length=40)


def clean_key(raw: str | None) -> str | None:
    """The visitor's key from the request header, or None. Malformed keys are rejected before any call."""
    if raw is None or not raw.strip():
        return None
    key = raw.strip()
    if not _KEY_PATTERN.match(key):
        raise HTTPException(status_code=400, detail="That doesn't look like a SerpApi key (letters and numbers only).")
    return key


def result_for(
    payload: dict[str, Any],
    *,
    keyword: str,
    location_name: str,
    language_name: str,
    search_volume: float | None,
    fetched_at: str,
    previous: PreviousCheck | None,
    source: str,
) -> dict[str, Any]:
    analysis = analyze_payload(payload, keyword, volume_override=search_volume, volume_source="user")
    if previous is None:
        changes: dict[str, Any] = {"has_previous": False, "current_fetched_at": fetched_at}
    else:
        changes = {
            **diff_snapshots(previous.snapshot.payload(), payload, keyword, search_volume, "user"),
            "previous_fetched_at": previous.fetched_at,
            "current_fetched_at": fetched_at,
        }
    return {
        "source": source,
        "mock_mode": False,
        "provider": str(payload.get("provider") or "serpapi"),
        "location_name": location_name,
        "language_name": language_name,
        **analysis,
        "changes": changes,
        "analysis_id": None,
        "analyzed_at": fetched_at,
        "own_key": True,
        # Kept by the browser so it can re-score or compare later without another search.
        "snapshot": {k: payload[k] for k in ("keyword", "provider", "items")},
        "snapshot_fetched_at": fetched_at,
    }


def analyze_with_own_key(
    api_key: str,
    *,
    keyword: str,
    location_name: str,
    language_name: str,
    search_volume: float | None,
    previous: PreviousCheck | None,
) -> dict[str, Any]:
    payload = SerpApiProvider().fetch_serp(keyword, location_name, language_name, api_key=api_key)
    return result_for(
        payload, keyword=keyword, location_name=location_name, language_name=language_name,
        search_volume=search_volume, fetched_at=utc_now(), previous=previous, source="api",
    )


class RescoreRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    location_name: str = Field("United States", max_length=100)
    language_name: str = Field("English", max_length=50)
    search_volume: float | None = Field(default=None, ge=0)
    snapshot: Snapshot
    snapshot_fetched_at: str = Field(..., max_length=40)
    previous: PreviousCheck | None = None


def rescore(request: RescoreRequest) -> dict[str, Any]:
    """Score a page the browser already has (no search, no key needed)."""
    return result_for(
        request.snapshot.payload(), keyword=request.keyword, location_name=request.location_name,
        language_name=request.language_name, search_volume=request.search_volume,
        fetched_at=request.snapshot_fetched_at, previous=request.previous, source="browser",
    )
