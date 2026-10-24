from fastapi.testclient import TestClient

from conftest import load_fixture

import providers.serpapi as serpapi
import store
import usage
from bulk import BULK_MAX_KEYWORDS
from main import app

client = TestClient(app)
SNAP = {"keyword": "x", "provider": "serpapi", "keyword_data": {}, "items": [{"type": "organic"}] * 5}


class FakeResponse:
    status_code = 200
    ok = True

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def use_fake_serpapi(monkeypatch, calls):
    monkeypatch.setenv("SERP_PROVIDER", "serpapi")
    monkeypatch.setenv("SERPAPI_API_KEY", "k")

    def fake_get(url, params, timeout):
        calls.append(params["q"])
        return FakeResponse(load_fixture("serpapi_roth_ira.json"))

    monkeypatch.setattr(serpapi.requests, "get", fake_get)


def test_preview_counts_cached_and_new_calls_without_spending():
    store.save_snapshot("cached kw", "United States", "English", False, SNAP)
    body = client.post("/bulk/preview", json={"keywords": [
        {"keyword": "cached kw"}, {"keyword": "new kw", "search_volume": 900}, {"keyword": "Cached KW "},
    ]}).json()

    assert body["total"] == 2 and body["duplicates_removed"] == 1
    assert body["cached"] == 1 and body["new_calls"] == 1
    assert body["without_volume"] == 1
    assert body["fits_in_cap"] is True
    assert body["remaining_calls"] == 50
    assert usage.calls_today() == 0


def test_preview_flags_runs_that_exceed_the_cap(monkeypatch):
    monkeypatch.setenv("MAX_API_CALLS_PER_DAY", "1")
    body = client.post("/bulk/preview", json={"keywords": [{"keyword": "a"}, {"keyword": "b"}]}).json()
    assert body["new_calls"] == 2 and body["fits_in_cap"] is False


def test_bulk_ranks_by_capturable_clicks_then_unknown_volume():
    body = client.post("/bulk/analyze", json={"mock_mode": True, "keywords": [
        {"keyword": "small", "search_volume": 100},
        {"keyword": "big", "search_volume": 50000},
        {"keyword": "medium", "search_volume": 5000},
    ]}).json()

    assert body["analyzed"] == 3 and body["errors"] == 0
    assert [r["keyword"] for r in body["results"]] == ["big", "medium", "small"]
    assert [r["rank"] for r in body["results"]] == [1, 2, 3]
    top = body["results"][0]["analysis"]
    assert top["volume_source"] == "user" and top["capturable_clicks"] > 0
    assert "report" in top  # full analysis, so the dashboard can open it


def test_bulk_uses_cache_and_counts_api_calls(monkeypatch):
    calls = []
    use_fake_serpapi(monkeypatch, calls)
    store.save_snapshot("already cached", "United States", "English", False, SNAP)

    body = client.post("/bulk/analyze", json={"keywords": [
        {"keyword": "already cached", "search_volume": 1000},
        {"keyword": "fresh one", "search_volume": 1000},
        {"keyword": "fresh two"},
    ]}).json()

    assert sorted(calls) == ["fresh one", "fresh two"]
    assert body["api_calls_used"] == 2
    sources = {r["keyword"]: r["analysis"]["source"] for r in body["results"]}
    assert sources == {"already cached": "cache", "fresh one": "api", "fresh two": "api"}
    assert body["results"][-1]["keyword"] == "fresh two"  # no volume ranks after known clicks
    assert len(client.get("/history?limit=10").json()) == 3


def test_bulk_stops_spending_at_daily_cap(monkeypatch):
    calls = []
    use_fake_serpapi(monkeypatch, calls)
    monkeypatch.setenv("MAX_API_CALLS_PER_DAY", "2")

    body = client.post("/bulk/analyze", json={"keywords": [{"keyword": f"kw {i}"} for i in range(4)]}).json()

    assert len(calls) == 2 and usage.calls_today() == 2
    assert body["analyzed"] == 2 and body["errors"] == 2 and body["cap_reached"] is True
    failed = [r for r in body["results"] if r["status"] == "error"]
    assert all(r["error_code"] == 429 and r["rank"] is None for r in failed)


def test_one_failing_keyword_does_not_sink_the_batch(monkeypatch):
    monkeypatch.setenv("SERP_PROVIDER", "serpapi")  # no key set -> 503 for keywords not in cache
    store.save_snapshot("cached kw", "United States", "English", False, SNAP)
    body = client.post("/bulk/analyze", json={"keywords": [{"keyword": "cached kw"}, {"keyword": "needs api"}]}).json()
    assert body["analyzed"] == 1 and body["errors"] == 1
    assert "SERPAPI_API_KEY" in body["results"][-1]["error"]


def test_bulk_limits_batch_size():
    too_many = [{"keyword": f"k{i}"} for i in range(BULK_MAX_KEYWORDS + 1)]
    assert client.post("/bulk/analyze", json={"keywords": too_many, "mock_mode": True}).status_code == 422
    assert client.post("/bulk/preview", json={"keywords": []}).status_code == 422
