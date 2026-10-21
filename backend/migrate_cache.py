"""One-time import of the pre-SQLite JSON cache (backend/cache/*.json + api_calls.log).

Imported files are moved to backend/cache/imported/, so this is a no-op on later starts.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import CACHE_DIR
from db import connect
from store import save_snapshot

log = logging.getLogger(__name__)

# The old cache keyed files by a hash, so location/language weren't stored; the UI always sent these.
DEFAULT_LOCATION = "United States"
DEFAULT_LANGUAGE = "English"


def _result_of(payload: dict[str, Any]) -> dict[str, Any] | None:
    if "items" in payload and "tasks" not in payload:
        return payload
    try:
        return payload["tasks"][0]["result"][0]
    except (KeyError, IndexError, TypeError):
        return None


def _is_mock(payload: dict[str, Any], result: dict[str, Any]) -> bool:
    if payload.get("provider") == "mock" or (result.get("keyword_data") or {}).get("source") == "mock":
        return True
    # Pre-provider mock payloads used example-N.com domains for every item.
    domains = [str(i.get("domain") or "") for i in result.get("items") or [] if isinstance(i, dict)]
    return bool(domains) and all(d.startswith("example-") for d in domains)


def _archive(path: Path) -> None:
    target = CACHE_DIR / "imported"
    target.mkdir(exist_ok=True)
    shutil.move(str(path), str(target / path.name))


def _import_snapshots() -> int:
    count = 0
    for path in sorted(CACHE_DIR.glob("*.json")):
        if path.name == "usage.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.warning("Skipping unreadable cache file %s", path.name)
            continue
        result = _result_of(payload)
        keyword = str((result or {}).get("keyword") or "").strip()
        if not result or not keyword:
            log.warning("Skipping cache file without a keyword: %s", path.name)
            continue
        payload.setdefault("provider", "dataforseo")
        fetched_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
        save_snapshot(keyword, DEFAULT_LOCATION, DEFAULT_LANGUAGE, _is_mock(payload, result), payload, fetched_at)
        _archive(path)
        count += 1
    return count


def _import_call_log() -> int:
    path = CACHE_DIR / "api_calls.log"
    if not path.exists():
        return 0
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
            rows.append((e["provider"], e["endpoint"], e["keyword"], e["at"]))
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    with connect() as conn:
        conn.executemany(
            "INSERT INTO api_calls (provider, endpoint, keyword, called_at) VALUES (?, ?, ?, ?)", rows
        )
    _archive(path)
    usage = CACHE_DIR / "usage.json"
    if usage.exists():
        _archive(usage)  # counts now come from api_calls
    return len(rows)


def import_json_cache() -> None:
    if not CACHE_DIR.exists():
        return
    snapshots = _import_snapshots()
    calls = _import_call_log()
    if snapshots or calls:
        log.info("Imported %d cached snapshots and %d API calls into SQLite", snapshots, calls)
