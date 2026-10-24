"""Sample data for the public demo, kept in git so a fresh server has keywords to show.

The demo reads saved (non-mock) results pages and their volumes. backend/data/ is gitignored, so a new
deployment starts with an empty database; on startup in DEMO_MODE, an empty database is filled from
demo_data/seed.json.

Refresh the seed from your local database:  python demo_seed.py export
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from config import BACKEND_DIR
from db import connect, init_db
from store import save_snapshot

log = logging.getLogger(__name__)

SEED_PATH: Path = BACKEND_DIR / "demo_data" / "seed.json"


def export_seed(path: Path = SEED_PATH) -> int:
    """Write every real results page and its volume to the seed file. Returns the number of snapshots."""
    with connect() as conn:
        snapshots = [
            dict(r) for r in conn.execute(
                "SELECT keyword, location, language, provider, payload, fetched_at FROM serp_snapshots "
                "WHERE mock_mode = 0 ORDER BY fetched_at, id"
            )
        ]
        volumes = [
            dict(r) for r in conn.execute(
                "SELECT v.keyword, v.location, v.language, v.search_volume, v.source, v.fetched_at "
                "FROM keyword_volume v WHERE EXISTS (SELECT 1 FROM serp_snapshots s WHERE s.mock_mode = 0 "
                "AND s.keyword = v.keyword AND s.location = v.location AND s.language = v.language) "
                "ORDER BY v.keyword"
            )
        ]
    for s in snapshots:
        s["payload"] = json.loads(s["payload"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"snapshots": snapshots, "volumes": volumes}, indent=1) + "\n", encoding="utf-8")
    return len(snapshots)


def load_seed_if_empty(path: Path = SEED_PATH) -> int:
    """Fill a database that has no real results pages from the seed. Returns the number of snapshots added."""
    if not path.exists():
        return 0
    with connect() as conn:
        if conn.execute("SELECT 1 FROM serp_snapshots WHERE mock_mode = 0 LIMIT 1").fetchone():
            return 0
    seed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    for s in seed.get("snapshots", []):
        save_snapshot(s["keyword"], s["location"], s["language"], False, s["payload"], fetched_at=s["fetched_at"])
    with connect() as conn:
        for v in seed.get("volumes", []):
            conn.execute(
                "INSERT OR REPLACE INTO keyword_volume (keyword, location, language, search_volume, source, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (v["keyword"], v["location"], v["language"], float(v["search_volume"]), v["source"], v["fetched_at"]),
            )
    count = len(seed.get("snapshots", []))
    log.info("Loaded %d demo snapshots from %s", count, path.name)
    return count


if __name__ == "__main__":
    if sys.argv[1:] != ["export"]:
        sys.exit("Usage: python demo_seed.py export")
    init_db()
    print(f"Wrote {export_seed()} snapshots to {SEED_PATH.relative_to(BACKEND_DIR)}")
