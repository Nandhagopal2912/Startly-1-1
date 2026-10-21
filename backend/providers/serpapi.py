"""SerpApi Google adapter: reports AI Overviews, which Serper does not (free tier: 250 searches/month)."""

from __future__ import annotations

from typing import Any

import requests
from fastapi import HTTPException

from config import env_clean
from providers.base import snapshot
from providers.serper import COUNTRY_CODES, LANGUAGE_CODES, domain_of
from usage import record_call

SEARCH_URL = "https://serpapi.com/search.json"

# SerpApi response key -> Startly item type (DataForSEO vocabulary). Lists add one item each.
LIST_FEATURES = {
    "organic_results": "organic",
    "ads": "paid",
    "shopping_results": "shopping",
}
# Keys that count as one SERP block regardless of how many entries they hold.
BLOCK_FEATURES = {
    "knowledge_graph": "knowledge_graph",
    "related_questions": "people_also_ask",
    "top_stories": "top_stories",
    "inline_images": "images",
    "inline_videos": "video",
    "local_results": "local_pack",
    "immersive_products": "shopping",
}


def normalize(data: dict[str, Any], keyword: str) -> dict[str, Any]:
    """Map a SerpApi engine=google response onto Startly's SERP snapshot shape."""
    items: list[dict[str, Any]] = []

    # Google sometimes lazy-loads the overview; SerpApi then returns only a page_token.
    # Either way the overview is on the page, so it counts without a second (paid) request.
    if data.get("ai_overview"):
        items.append({"type": "ai_overview", "rank_group": 0, "domain": None})

    answer = data.get("answer_box")
    if isinstance(answer, dict) and answer:
        kind = "featured_snippet" if answer.get("link") else "answer_box"
        items.append({"type": kind, "rank_group": 0, "domain": domain_of(answer.get("link"))})

    for key, item_type in BLOCK_FEATURES.items():
        if data.get(key):
            items.append({"type": item_type, "rank_group": None, "domain": None})

    for key, item_type in LIST_FEATURES.items():
        for entry in data.get(key) or []:
            if isinstance(entry, dict):
                items.append({
                    "type": item_type,
                    "rank_group": entry.get("position"),
                    "domain": domain_of(entry.get("link")),
                })

    return snapshot(keyword, SerpApiProvider.name, items)


class SerpApiProvider:
    name = "serpapi"

    def is_configured(self) -> bool:
        return env_clean("SERPAPI_API_KEY") is not None

    def fetch_serp(self, keyword: str, location_name: str, language_name: str) -> dict[str, Any]:
        api_key = env_clean("SERPAPI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="SerpApi is not configured. Set SERPAPI_API_KEY in backend/.env (free key at serpapi.com).",
            )
        record_call(self.name, "search", keyword)
        params = {
            "engine": "google",
            "q": keyword,
            "gl": COUNTRY_CODES.get(location_name.strip().lower(), "us"),
            "hl": LANGUAGE_CODES.get(language_name.strip().lower(), "en"),
            "api_key": api_key,
        }
        try:
            res = requests.get(SEARCH_URL, params=params, timeout=40)
        except requests.RequestException as exc:
            # Message deliberately omits the URL, which carries the API key.
            raise HTTPException(status_code=502, detail=f"SerpApi request failed: {type(exc).__name__}") from exc
        try:
            data = res.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=f"SerpApi returned invalid JSON (HTTP {res.status_code}).") from exc
        if not res.ok or data.get("error"):
            message = data.get("error") or f"HTTP {res.status_code}"
            # "Google hasn't returned any results" is a valid, empty SERP rather than a failure.
            if "hasn't returned any results" in str(message):
                return snapshot(keyword, self.name, [])
            raise HTTPException(status_code=502, detail=f"SerpApi error: {message}")
        return normalize(data, keyword)
