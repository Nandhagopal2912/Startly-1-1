from __future__ import annotations

import json

from fastapi.testclient import TestClient

import demo_seed
import store
from main import app

PAYLOAD = {"keyword": "devops", "provider": "serpapi", "keyword_data": {}, "items": []}


def test_export_keeps_real_pages_only(tmp_path):
    store.save_snapshot("DevOps", "United States", "English", False, PAYLOAD)
    store.save_snapshot("free crm", "United States", "English", True, {**PAYLOAD, "provider": "mock"})
    store.save_volume("devops", "United States", "English", 5000, "user")
    store.save_volume("free crm", "United States", "English", 900, "user")
    path = tmp_path / "seed.json"

    assert demo_seed.export_seed(path) == 1
    seed = json.loads(path.read_text(encoding="utf-8"))
    assert [s["keyword"] for s in seed["snapshots"]] == ["devops"]
    assert [v["keyword"] for v in seed["volumes"]] == ["devops"]


def test_load_fills_only_an_empty_database(tmp_path):
    path = tmp_path / "seed.json"
    path.write_text(json.dumps({
        "snapshots": [{"keyword": "devops", "location": "united states", "language": "english",
                       "provider": "serpapi", "payload": PAYLOAD, "fetched_at": "2026-10-21T14:14:34+00:00"}],
        "volumes": [{"keyword": "devops", "location": "united states", "language": "english",
                     "search_volume": 5000, "source": "user", "fetched_at": "2026-10-21T14:14:34+00:00"}],
    }), encoding="utf-8")

    assert demo_seed.load_seed_if_empty(path) == 1
    assert demo_seed.load_seed_if_empty(path) == 0  # already filled: nothing duplicated
    assert store.get_volume("devops", "United States", "English") == (5000.0, "user")


def test_demo_server_starts_with_the_committed_samples(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    with TestClient(app) as client:  # runs the startup hook
        keywords = {k["keyword"].lower() for k in client.get("/demo/keywords").json()}
    assert keywords and "devops" in keywords
