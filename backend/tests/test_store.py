import json
import os
import time

from fastapi.testclient import TestClient

from conftest import load_fixture

import migrate_cache
import store
import usage
from db import connect
from main import app

client = TestClient(app)
SNAP = {"keyword": "crm", "provider": "serper", "keyword_data": {}, "items": [{"type": "organic"}]}


def test_snapshot_lookup_is_case_insensitive_and_separates_mock():
    store.save_snapshot("CRM ", "United States", "English", False, SNAP)
    assert store.latest_snapshot("crm", "united states", "english", False) is not None
    assert store.latest_snapshot("crm", "United States", "English", True) is None


def test_expired_snapshot_is_ignored(monkeypatch):
    store.save_snapshot("crm", "US", "en", False, SNAP, fetched_at="2020-01-01T00:00:00+00:00")
    assert store.latest_snapshot("crm", "US", "en", False) is None
    monkeypatch.setenv("CACHE_TTL_DAYS", "0")  # never expire
    assert store.latest_snapshot("crm", "US", "en", False) is not None


def test_newest_snapshot_wins():
    store.save_snapshot("crm", "US", "en", False, {**SNAP, "provider": "old"}, fetched_at="2099-01-01T00:00:00+00:00")
    store.save_snapshot("crm", "US", "en", False, {**SNAP, "provider": "new"}, fetched_at="2099-02-01T00:00:00+00:00")
    assert store.latest_snapshot("crm", "US", "en", False)[1]["provider"] == "new"


def test_user_volume_is_remembered_for_next_analysis():
    first = client.post("/analyze", json={"keyword": "crm", "mock_mode": True, "search_volume": 4321}).json()
    assert first["raw_volume"] == 4321 and first["volume_source"] == "user"

    again = client.post("/analyze", json={"keyword": "crm", "mock_mode": True}).json()
    assert again["source"] == "cache"
    assert again["raw_volume"] == 4321
    assert again["volume_source"] == "user"


def test_history_lists_analyses_newest_first():
    client.post("/analyze", json={"keyword": "alpha", "mock_mode": True})
    client.post("/analyze", json={"keyword": "beta", "mock_mode": True})
    rows = client.get("/history?limit=10").json()
    assert [r["keyword"] for r in rows[:2]] == ["beta", "alpha"]
    assert rows[0]["provider"] == "mock"
    assert rows[0]["adjusted_volume"] > 0


def test_api_calls_counted_in_database():
    usage.record_call("serpapi", "search", "a")
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0] == 1
    assert usage.calls_today() == 1


def test_json_cache_is_imported_once(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(migrate_cache, "CACHE_DIR", cache_dir)

    serpapi_snap = {"keyword": "what is a roth ira", "provider": "serpapi", "keyword_data": {},
                    "items": [{"type": "ai_overview"}, {"type": "organic"}]}
    (cache_dir / "aaa.json").write_text(json.dumps(serpapi_snap), encoding="utf-8")
    legacy = load_fixture("dataforseo_serp.json")  # pre-provider DataForSEO format
    (cache_dir / "bbb.json").write_text(json.dumps(legacy), encoding="utf-8")
    (cache_dir / "usage.json").write_text('{"2026-10-21": 1}', encoding="utf-8")
    now = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    (cache_dir / "api_calls.log").write_text(
        json.dumps({"at": now, "provider": "serpapi", "endpoint": "search", "keyword": "what is a roth ira"}) + "\n",
        encoding="utf-8",
    )
    os.utime(cache_dir / "aaa.json")  # fresh mtime -> within TTL

    migrate_cache.import_json_cache()

    found = store.latest_snapshot("What is a Roth IRA", "United States", "English", False)
    assert found is not None and found[1]["provider"] == "serpapi"
    legacy_found = store.latest_snapshot("running shoes", "United States", "English", False)
    assert legacy_found is not None and legacy_found[1]["provider"] == "dataforseo"
    assert usage.calls_today() == 1
    assert sorted(p.name for p in (cache_dir / "imported").iterdir()) == ["aaa.json", "api_calls.log", "bbb.json", "usage.json"]

    migrate_cache.import_json_cache()  # second run finds nothing new
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM serp_snapshots").fetchone()[0] == 2


def test_history_stores_click_range():
    client.post("/analyze", json={"keyword": "gamma", "mock_mode": True, "search_volume": 10000})
    row = client.get("/history?limit=1").json()[0]
    assert row["capturable_clicks_low"] is not None
    assert row["capturable_clicks_low"] <= row["adjusted_volume"] <= row["capturable_clicks_high"]


def test_old_database_gets_new_columns(tmp_path, monkeypatch):
    import sqlite3

    import db

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute(
        "CREATE TABLE analyses (id INTEGER PRIMARY KEY, keyword TEXT NOT NULL, location TEXT NOT NULL, "
        "language TEXT NOT NULL, snapshot_id INTEGER, provider TEXT NOT NULL, raw_volume REAL NOT NULL, "
        "volume_source TEXT NOT NULL, adjusted_volume REAL NOT NULL, penalty_percent INTEGER NOT NULL, "
        "organic_results INTEGER NOT NULL, total_results INTEGER NOT NULL, created_at TEXT NOT NULL)"
    )
    old.execute("INSERT INTO analyses VALUES (1,'old','us','en',NULL,'serper',100,'user',55,45,6,10,'2026-01-01')")
    old.commit()
    old.close()

    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()
    rows = store.recent_analyses(5)
    assert rows[0]["keyword"] == "old" and rows[0]["capturable_clicks_low"] is None
