from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from config import CACHE_DIR, cache_ttl_days


def cache_key(keyword: str, location_name: str, language_name: str, mock_mode: bool) -> str:
    base = f"{keyword.strip().lower()}::{location_name.strip().lower()}::{language_name.strip().lower()}::{mock_mode}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def load_cached_response(key: str) -> dict[str, Any] | None:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    ttl_days = cache_ttl_days()
    if ttl_days > 0 and time.time() - path.stat().st_mtime > ttl_days * 86400:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_cached_response(key: str, payload: dict[str, Any]) -> None:
    path = CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
