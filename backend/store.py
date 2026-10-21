"""Read/write SERP snapshots, volumes and analyses in SQLite."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from config import cache_ttl_days
from db import connect, norm, utc_now


def _fresh_after() -> str | None:
    """Oldest fetched_at still considered fresh, or None when cache never expires."""
    days = cache_ttl_days()
    if days <= 0:
        return None
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


def latest_snapshot(keyword: str, location: str, language: str, mock_mode: bool) -> tuple[int, dict[str, Any]] | None:
    """Newest fresh snapshot as (id, payload), or None if there is none."""
    sql = (
        "SELECT id, payload FROM serp_snapshots "
        "WHERE keyword = ? AND location = ? AND language = ? AND mock_mode = ?"
    )
    params: list[Any] = [norm(keyword), norm(location), norm(language), int(mock_mode)]
    cutoff = _fresh_after()
    if cutoff:
        sql += " AND fetched_at >= ?"
        params.append(cutoff)
    sql += " ORDER BY fetched_at DESC, id DESC LIMIT 1"
    with connect() as conn:
        row = conn.execute(sql, params).fetchone()
    return (row["id"], json.loads(row["payload"])) if row else None


def save_snapshot(
    keyword: str, location: str, language: str, mock_mode: bool, payload: dict[str, Any],
    fetched_at: str | None = None,
) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO serp_snapshots (keyword, location, language, mock_mode, provider, payload, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                norm(keyword), norm(location), norm(language), int(mock_mode),
                str(payload.get("provider") or "unknown"), json.dumps(payload), fetched_at or utc_now(),
            ),
        )
        return int(cur.lastrowid)


def get_volume(keyword: str, location: str, language: str) -> tuple[float, str] | None:
    """Stored (search_volume, source). User-entered volumes never expire; API volumes follow the cache TTL."""
    with connect() as conn:
        row = conn.execute(
            "SELECT search_volume, source, fetched_at FROM keyword_volume "
            "WHERE keyword = ? AND location = ? AND language = ?",
            (norm(keyword), norm(location), norm(language)),
        ).fetchone()
    if row is None:
        return None
    cutoff = _fresh_after()
    if row["source"] != "user" and cutoff and row["fetched_at"] < cutoff:
        return None
    return float(row["search_volume"]), str(row["source"])


def save_volume(keyword: str, location: str, language: str, volume: float, source: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO keyword_volume (keyword, location, language, search_volume, source, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (keyword, location, language) DO UPDATE SET "
            "search_volume = excluded.search_volume, source = excluded.source, fetched_at = excluded.fetched_at",
            (norm(keyword), norm(location), norm(language), float(volume), source, utc_now()),
        )


def record_analysis(
    *, keyword: str, location: str, language: str, snapshot_id: int, provider: str, analysis: dict[str, Any]
) -> None:
    summary = analysis["report"]["summary"]
    with connect() as conn:
        conn.execute(
            "INSERT INTO analyses (keyword, location, language, snapshot_id, provider, raw_volume, volume_source, "
            "adjusted_volume, capturable_clicks_low, capturable_clicks_high, penalty_percent, organic_results, "
            "total_results, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                analysis["keyword"], location, language, snapshot_id, provider,
                analysis["raw_volume"], analysis["volume_source"], analysis["adjusted_volume"],
                analysis.get("capturable_clicks_low"), analysis.get("capturable_clicks_high"),
                summary["penalty_percent"], analysis["organic_results"], analysis["total_results"], utc_now(),
            ),
        )


def recent_analyses(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT keyword, location, language, provider, raw_volume, volume_source, adjusted_volume, "
            "capturable_clicks_low, capturable_clicks_high, penalty_percent, organic_results, total_results, created_at "
            "FROM analyses ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
