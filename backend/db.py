"""SQLite storage: SERP snapshots, search volumes, analyses and paid API calls."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from config import BACKEND_DIR

DB_PATH: Path = BACKEND_DIR / "data" / "startly.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS serp_snapshots (
    id          INTEGER PRIMARY KEY,
    keyword     TEXT    NOT NULL,  -- normalized: trimmed + lowercase
    location    TEXT    NOT NULL,
    language    TEXT    NOT NULL,
    mock_mode   INTEGER NOT NULL DEFAULT 0,
    provider    TEXT    NOT NULL,
    payload     TEXT    NOT NULL,  -- JSON snapshot (see providers/base.py)
    fetched_at  TEXT    NOT NULL   -- ISO 8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_snapshots_lookup
    ON serp_snapshots (keyword, location, language, mock_mode, fetched_at);

CREATE TABLE IF NOT EXISTS keyword_volume (
    keyword        TEXT NOT NULL,
    location       TEXT NOT NULL,
    language       TEXT NOT NULL,
    search_volume  REAL NOT NULL,
    source         TEXT NOT NULL,  -- user | dataforseo | ...
    fetched_at     TEXT NOT NULL,
    PRIMARY KEY (keyword, location, language)
);

CREATE TABLE IF NOT EXISTS analyses (
    id               INTEGER PRIMARY KEY,
    keyword          TEXT    NOT NULL,
    location         TEXT    NOT NULL,
    language         TEXT    NOT NULL,
    snapshot_id      INTEGER REFERENCES serp_snapshots (id),
    provider         TEXT    NOT NULL,
    raw_volume       REAL    NOT NULL,
    volume_source    TEXT    NOT NULL,
    adjusted_volume  REAL    NOT NULL,
    penalty_percent  INTEGER NOT NULL,
    organic_results  INTEGER NOT NULL,
    total_results    INTEGER NOT NULL,
    created_at       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses (created_at);

CREATE TABLE IF NOT EXISTS api_calls (
    id        INTEGER PRIMARY KEY,
    provider  TEXT NOT NULL,
    endpoint  TEXT NOT NULL,
    keyword   TEXT NOT NULL,
    called_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_api_calls_at ON api_calls (called_at);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def norm(text: str) -> str:
    return text.strip().lower()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Short-lived connection per operation; commits on success, rolls back on error."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Columns added after the first release: (table, column, definition). Applied once to older databases.
ADDED_COLUMNS = [
    ("analyses", "capturable_clicks_low", "REAL"),
    ("analyses", "capturable_clicks_high", "REAL"),
]


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        for table, column, definition in ADDED_COLUMNS:
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
