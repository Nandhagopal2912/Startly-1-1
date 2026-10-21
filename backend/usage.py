"""Daily cap and log for outbound paid API calls, so a bug can't drain credits."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from config import CACHE_DIR, daily_api_cap

_USAGE_FILE = CACHE_DIR / "usage.json"
_LOG_FILE = CACHE_DIR / "api_calls.log"
_lock = threading.Lock()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_usage(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def calls_today() -> int:
    return int(_read_usage(_USAGE_FILE).get(_today(), 0))


def record_call(provider: str, endpoint: str, keyword: str) -> None:
    """Count one paid call; raise 429 instead if today's cap is already used up."""
    cap = daily_api_cap()
    with _lock:
        usage = _read_usage(_USAGE_FILE)
        today = _today()
        used = int(usage.get(today, 0))
        if used >= cap:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Daily API cap reached ({used}/{cap} calls). Use mock mode or cached keywords, "
                    "or raise MAX_API_CALLS_PER_DAY in backend/.env."
                ),
            )
        usage[today] = used + 1
        _USAGE_FILE.write_text(json.dumps(usage, indent=2), encoding="utf-8")
        entry = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "provider": provider,
            "endpoint": endpoint,
            "keyword": keyword,
        }
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
