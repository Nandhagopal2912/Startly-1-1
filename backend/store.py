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
) -> tuple[int, str]:
    """Save an analysis (summary columns + the full response as JSON). Returns (id, created_at)."""
    summary = analysis["report"]["summary"]
    created_at = utc_now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO analyses (keyword, location, language, snapshot_id, provider, raw_volume, volume_source, "
            "adjusted_volume, capturable_clicks_low, capturable_clicks_high, penalty_percent, organic_results, "
            "total_results, created_at, result) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                analysis["keyword"], location, language, snapshot_id, provider,
                analysis["raw_volume"], analysis["volume_source"], analysis["adjusted_volume"],
                analysis.get("capturable_clicks_low"), analysis.get("capturable_clicks_high"),
                summary["penalty_percent"], analysis["organic_results"], analysis["total_results"], created_at,
                json.dumps(analysis),
            ),
        )
        return int(cur.lastrowid), created_at


_SUMMARY_COLUMNS = (
    "id, keyword, location, language, provider, raw_volume, volume_source, adjusted_volume, "
    "capturable_clicks_low, capturable_clicks_high, penalty_percent, organic_results, total_results, created_at"
)


def recent_analyses(limit: int = 50, offset: int = 0, query: str | None = None) -> list[dict[str, Any]]:
    """Analysis summaries, newest first; `query` filters by keyword substring (case-insensitive)."""
    # exact = the full result was saved, so reopening shows it unchanged (older rows are re-scored on open)
    sql = f"SELECT {_SUMMARY_COLUMNS}, result IS NOT NULL AS exact FROM analyses"
    params: list[Any] = []
    if query and query.strip():
        sql += " WHERE lower(keyword) LIKE ? ESCAPE '!'"
        escaped = norm(query).replace("!", "!!").replace("%", "!%").replace("_", "!_")
        params.append(f"%{escaped}%")
    sql += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{**dict(r), "exact": bool(r["exact"])} for r in rows]


def analysis_row(analysis_id: int) -> dict[str, Any] | None:
    """One analyses row including the stored JSON result (None for analyses saved before it existed)."""
    with connect() as conn:
        row = conn.execute(
            f"SELECT {_SUMMARY_COLUMNS}, snapshot_id, result FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
    return dict(row) if row else None


def latest_analysis_ids(limit: int = 20, after_id: int = 0) -> list[int]:
    """Newest analysis id per keyword/location/language (ids above `after_id` only), most recent first."""
    sql = (
        "SELECT MAX(id) AS id FROM analyses WHERE id > ? "
        "GROUP BY lower(keyword), location, language ORDER BY id DESC LIMIT ?"
    )
    params: list[Any] = [after_id, limit]
    with connect() as conn:
        return [int(r["id"]) for r in conn.execute(sql, params).fetchall()]


def snapshot_by_id(snapshot_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT payload FROM serp_snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    return json.loads(row["payload"]) if row else None
