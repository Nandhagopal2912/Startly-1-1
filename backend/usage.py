"""Daily cap and log for outbound paid API calls, so a bug can't drain credits."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from config import daily_api_cap
from db import connect, utc_now


def _start_of_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")


def calls_today() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) FROM api_calls WHERE called_at >= ?", (_start_of_today(),)).fetchone()
    return int(row[0])


def record_call(provider: str, endpoint: str, keyword: str) -> None:
    """Count one paid call; raise 429 instead if today's cap is already used up."""
    cap = daily_api_cap()
    with connect() as conn:
        # Take the write lock before counting so two requests can't both slip under the cap.
        conn.execute("BEGIN IMMEDIATE")
        used = int(conn.execute(
            "SELECT COUNT(*) FROM api_calls WHERE called_at >= ?", (_start_of_today(),)
        ).fetchone()[0])
        if used >= cap:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Daily API cap reached ({used}/{cap} calls). Use mock mode or cached keywords, "
                    "or raise MAX_API_CALLS_PER_DAY in backend/.env."
                ),
            )
        conn.execute(
            "INSERT INTO api_calls (provider, endpoint, keyword, called_at) VALUES (?, ?, ?, ?)",
            (provider, endpoint, keyword, utc_now()),
        )


def calls_by_provider_today() -> dict[str, int]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT provider, COUNT(*) AS n FROM api_calls WHERE called_at >= ? GROUP BY provider", (_start_of_today(),)
        ).fetchall()
    return {r["provider"]: int(r["n"]) for r in rows}
