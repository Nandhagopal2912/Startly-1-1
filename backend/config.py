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
    """Which SERP source to use: serper | serpapi | dataforseo | mock."""
    return (env_clean("SERP_PROVIDER") or "serper").lower()


def volume_provider_name() -> str:
    """Which search-volume source to use: dataforseo | none."""
    return (env_clean("VOLUME_PROVIDER") or "none").lower()


def daily_api_cap() -> int:
    """Max outbound paid API calls per day (0 = block all live calls)."""
    return env_int("MAX_API_CALLS_PER_DAY", 50)


def cache_ttl_days() -> int:
    return env_int("CACHE_TTL_DAYS", 7)


def env_bool(name: str, default: bool = False) -> bool:
    raw = env_clean(name)
    return default if raw is None else raw.lower() in {"1", "true", "yes", "on"}


def demo_mode() -> bool:
    """Public demo: serve saved analyses only. No provider calls, no writes to the database."""
    return env_bool("DEMO_MODE")


def allowed_origins() -> list[str]:
    """Browser origins allowed to call the API (comma-separated ALLOWED_ORIGINS)."""
    raw = env_clean("ALLOWED_ORIGINS") or "http://localhost:3000,http://127.0.0.1:3000"
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def rate_limit_per_minute() -> int:
    """Requests per client IP per minute (0 = no limit)."""
    return env_int("RATE_LIMIT_PER_MINUTE", 120)


def trust_proxy_headers() -> bool:
    """Read the client IP from X-Forwarded-For; only enable behind a proxy that sets it (most hosts do)."""
    return env_bool("TRUST_PROXY_HEADERS")
