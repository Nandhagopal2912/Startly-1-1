from __future__ import annotations

import json
import logging
from typing import Any

import requests
from fastapi import HTTPException

from config import env_clean
from providers.base import snapshot
from usage import record_call

log = logging.getLogger(__name__)

SERP_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
KEYWORDS_DATA_URL = "https://api.dataforseo.com/v3/keywords_data/google/search_volume/live"


def credentials() -> tuple[str, str] | None:
    """DataForSEO Basic auth: email (login) + API password from the dashboard."""
    email = env_clean("DATAFORSEO_EMAIL") or env_clean("DATAFORSEO_LOGIN")
    password = env_clean("DATAFORSEO_PASSWORD")
    return (email, password) if email and password else None


def _require_credentials() -> tuple[str, str]:
    creds = credentials()
    if creds is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "DataForSEO is not configured. Set DATAFORSEO_EMAIL and DATAFORSEO_PASSWORD "
                "in backend/.env and restart the server, or switch SERP_PROVIDER."
            ),
        )
    return creds


def raise_if_api_error(payload: dict[str, Any]) -> None:
    """DataForSEO returns HTTP 200 with status_code 20000 = OK; other codes mean failure."""
    root_code = payload.get("status_code")
    root_msg = str(payload.get("status_message", ""))
    if root_code is not None and root_code != 20000:
        raise HTTPException(status_code=502, detail=f"DataForSEO API error {root_code}: {root_msg or 'no message'}")

    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks or not isinstance(tasks[0], dict):
        raise HTTPException(status_code=502, detail="DataForSEO returned no tasks in the response.")

    task = tasks[0]
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
        raise HTTPException(status_code=502, detail=f"DataForSEO returned no result items. Task message: {task_msg or 'none'}")


def normalize_serp(payload: dict[str, Any], keyword: str) -> dict[str, Any]:
    result = payload["tasks"][0]["result"][0]
    items = [
        {"type": item.get("type"), "rank_group": item.get("rank_group"), "domain": item.get("domain")}
        for item in result.get("items") or []
        if isinstance(item, dict)
    ]
    return snapshot(str(result.get("keyword") or keyword), DataForSeoProvider.name, items)


def _post(url: str, body: list[dict[str, Any]], timeout: int) -> dict[str, Any]:
    login, password = _require_credentials()
    try:
        res = requests.post(url, auth=(login, password), json=body, timeout=timeout)
        res.raise_for_status()
        return res.json()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"DataForSEO HTTP request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="DataForSEO returned invalid JSON.") from exc


class DataForSeoProvider:
    name = "dataforseo"

    def is_configured(self) -> bool:
        return credentials() is not None

    def fetch_serp(self, keyword: str, location_name: str, language_name: str) -> dict[str, Any]:
        _require_credentials()
        record_call(self.name, "serp", keyword)
        payload = _post(
            SERP_URL,
            [{"keyword": keyword, "location_name": location_name, "language_name": language_name}],
            timeout=40,
        )
        raise_if_api_error(payload)
        return normalize_serp(payload, keyword)

    def fetch_volume(self, keyword: str, location_name: str, language_name: str) -> float | None:
        """Search volume, or None when DataForSEO has no data for the keyword."""
        _require_credentials()
        record_call(self.name, "search_volume", keyword)
        # Keywords API expects 'keywords' as an array, not 'keyword'
        data = _post(
            KEYWORDS_DATA_URL,
            [{"keywords": [keyword], "location_name": location_name, "language_name": language_name}],
            timeout=20,
        )
        if data.get("status_code") != 20000:
            log.warning("DataForSEO volume error %s: %s", data.get("status_code"), data.get("status_message"))
            return None
        try:
            volume = data["tasks"][0]["result"][0].get("search_volume")
        except (KeyError, IndexError, TypeError):
            log.warning("DataForSEO volume response had no result for %r", keyword)
            return None
        return float(volume) if volume is not None else None
