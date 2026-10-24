"""Credits left on the server's own API keys (from .env), for the owner's dashboard. Never returns the keys."""

from __future__ import annotations

import threading
import time
from typing import Any

from fastapi import HTTPException

import config
from config import env_clean
from providers.serpapi import account_info as serpapi_account
from providers.serper import account_balance as serper_account
from usage import calls_by_provider_today

CACHE_SECONDS = 60
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_lock = threading.Lock()

PROVIDERS = {
    "serpapi": {"label": "SerpApi", "env": "SERPAPI_API_KEY", "dashboard": "https://serpapi.com/dashboard"},
    "serper": {"label": "Serper", "env": "SERPER_API_KEY", "dashboard": "https://serper.dev/dashboard"},
}


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _lookup(name: str, key: str) -> dict[str, Any]:
    """Ask the provider (free calls on both); errors become a message instead of failing the whole response."""
    try:
        if name == "serpapi":
            info = serpapi_account(key)
            return {"credits_left": info["searches_left"], "plan": info["plan_name"],
                    "credits_per_month": info["searches_per_month"], "error": None}
        info = serper_account(key)
        return {"credits_left": info["credits_left"], "plan": None, "credits_per_month": None, "error": None}
    except HTTPException as exc:
        return {"credits_left": None, "plan": None, "credits_per_month": None, "error": str(exc.detail)}


def server_credits(refresh: bool = False) -> dict[str, Any]:
    if config.demo_mode():
        # The public demo doesn't use the owner's keys, and visitors shouldn't see the owner's balances.
        return {"demo": True, "providers": []}
    active = config.serp_provider_name()
    used_today = calls_by_provider_today()
    out = []
    for name, meta in PROVIDERS.items():
        key = env_clean(meta["env"])
        entry: dict[str, Any] = {
            "provider": name, "label": meta["label"], "active": name == active, "configured": bool(key),
            "dashboard": meta["dashboard"], "used_today": used_today.get(name, 0),
            "credits_left": None, "plan": None, "credits_per_month": None, "error": None, "checked_at": None,
        }
        if key:
            with _lock:
                cached = _cache.get(name)
            if cached and not refresh and time.time() - cached[0] < CACHE_SECONDS:
                entry.update(cached[1])
            else:
                result = {**_lookup(name, key), "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                with _lock:
                    _cache[name] = (time.time(), result)
                entry.update(result)
        out.append(entry)
    return {"demo": False, "providers": out, "daily_cap": config.daily_api_cap(), "calls_today": sum(used_today.values())}
