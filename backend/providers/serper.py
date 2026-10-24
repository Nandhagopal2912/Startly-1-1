"""Serper.dev Google SERP adapter (has a free tier; no search volume)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests
from fastapi import HTTPException

from config import env_clean
from providers.base import snapshot
from usage import record_call

SEARCH_URL = "https://google.serper.dev/search"

# Serper takes ISO codes; Startly's API takes DataForSEO-style names.
COUNTRY_CODES = {
    "united states": "us", "united kingdom": "uk", "india": "in", "canada": "ca",
    "australia": "au", "germany": "de", "france": "fr", "spain": "es", "italy": "it",
    "netherlands": "nl", "brazil": "br", "mexico": "mx", "japan": "jp", "singapore": "sg",
    "united arab emirates": "ae", "south africa": "za", "new zealand": "nz", "ireland": "ie",
}
LANGUAGE_CODES = {
    "english": "en", "hindi": "hi", "tamil": "ta", "german": "de", "french": "fr",
    "spanish": "es", "italian": "it", "dutch": "nl", "portuguese": "pt", "japanese": "ja",
}

# Serper response key -> Startly item type (DataForSEO vocabulary). Lists add one item each.
LIST_FEATURES = {
    "organic": "organic",
    "ads": "paid",
    "shopping": "shopping",
}
# Keys that count as one SERP block regardless of how many entries they hold.
BLOCK_FEATURES = {
    "knowledgeGraph": "knowledge_graph",
    "aiOverview": "ai_overview",
    "peopleAlsoAsk": "people_also_ask",
    "topStories": "top_stories",
    "images": "images",
    "videos": "video",
    "places": "local_pack",
}


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host or None


def normalize(data: dict[str, Any], keyword: str) -> dict[str, Any]:
    """Map a Serper /search response onto Startly's SERP snapshot shape."""
    items: list[dict[str, Any]] = []

    answer = data.get("answerBox")
    if isinstance(answer, dict) and answer:
        # A snippet quoting a page still sends some clicks; a bare answer usually doesn't.
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

    return snapshot(keyword, SerperProvider.name, items)


class SerperProvider:
    name = "serper"

    def is_configured(self) -> bool:
        return env_clean("SERPER_API_KEY") is not None

    def fetch_serp(self, keyword: str, location_name: str, language_name: str) -> dict[str, Any]:
        api_key = env_clean("SERPER_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="Serper is not configured. Set SERPER_API_KEY in backend/.env (free key at serper.dev).",
            )
        record_call(self.name, "search", keyword)
        body = {
            "q": keyword,
            "gl": COUNTRY_CODES.get(location_name.strip().lower(), "us"),
            "hl": LANGUAGE_CODES.get(language_name.strip().lower(), "en"),
            "num": 10,
        }
        try:
            res = requests.post(
                SEARCH_URL,
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"Serper request failed: {exc}") from exc
        if res.status_code in (401, 403):
            raise HTTPException(status_code=502, detail="Serper rejected the API key (check SERPER_API_KEY or remaining credits).")
        if not res.ok:
            raise HTTPException(status_code=502, detail=f"Serper error {res.status_code}: {res.text[:200]}")
        try:
            data = res.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Serper returned invalid JSON.") from exc
        return normalize(data, keyword)


ACCOUNT_URL = "https://google.serper.dev/account"


def account_balance(api_key: str) -> dict[str, Any]:
    """Credits left on a Serper key. Not in Serper's docs (found by testing), so callers treat it as best-effort."""
    try:
        res = requests.get(ACCOUNT_URL, headers={"X-API-KEY": api_key}, timeout=15)
        data = res.json()
    except (requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Couldn't read the Serper balance: {type(exc).__name__}") from exc
    if not res.ok or "balance" not in data:
        raise HTTPException(status_code=502, detail="Serper didn't return a balance. Check it at serper.dev/dashboard.")
    return {"credits_left": data.get("balance"), "rate_limit_per_second": data.get("rateLimit")}
