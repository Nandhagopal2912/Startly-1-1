from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
# Load backend/.env first, then optional cwd .env (helps if uvicorn cwd differs).
load_dotenv(BACKEND_DIR / ".env")
load_dotenv()

CACHE_DIR = BACKEND_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def env_clean(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    s = value.strip().replace("﻿", "").strip()
    return s or None


def env_int(name: str, default: int) -> int:
    raw = env_clean(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def serp_provider_name() -> str:
    """Which SERP source to use: serper | dataforseo | mock."""
    return (env_clean("SERP_PROVIDER") or "serper").lower()


def volume_provider_name() -> str:
    """Which search-volume source to use: dataforseo | none."""
    return (env_clean("VOLUME_PROVIDER") or "none").lower()


def daily_api_cap() -> int:
    """Max outbound paid API calls per day (0 = block all live calls)."""
    return env_int("MAX_API_CALLS_PER_DAY", 50)


def cache_ttl_days() -> int:
    return env_int("CACHE_TTL_DAYS", 7)
