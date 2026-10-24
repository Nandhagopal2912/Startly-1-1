from fastapi.testclient import TestClient

from conftest import load_fixture

import providers.serper as serper
import usage
from main import app

client = TestClient(app)


class FakeResponse:
    status_code = 200
    ok = True
    text = ""

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def test_mock_mode_works_without_any_keys():
    res = client.post("/analyze", json={"keyword": "crm", "mock_mode": True})
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "mock"
    assert body["source"] == "api"
    assert body["raw_volume"] > 0
    assert usage.calls_today() == 0

    again = client.post("/analyze", json={"keyword": "crm", "mock_mode": True})
    assert again.json()["source"] == "cache"


def test_serper_flow_with_user_volume_and_cache(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-key")
    calls = []

    def fake_post(url, **kwargs):
        calls.append(kwargs["json"])
        return FakeResponse(load_fixture("serper_best_crm.json"))

    monkeypatch.setattr(serper.requests, "post", fake_post)

    res = client.post("/analyze", json={"keyword": "best crm software", "search_volume": 10000})
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "serper"
    assert body["volume_source"] == "user"
    # Only the 2 ads cost clicks; knowledge panel, snippet and PAA are neutral in the click model.
    assert body["report"]["summary"]["penalty_percent"] == 13
    assert body["capturable_clicks"] == body["adjusted_volume"] == 3902
    assert calls[0]["gl"] == "us"

    cached = client.post("/analyze", json={"keyword": "best crm software", "search_volume": 10000})
    assert cached.json()["source"] == "cache"
    assert len(calls) == 1
    assert usage.calls_today() == 1


def test_missing_serper_key_returns_clear_error():
    res = client.post("/analyze", json={"keyword": "anything"})
    assert res.status_code == 503
    assert "SERPER_API_KEY" in res.json()["detail"]


def test_provider_health():
    body = client.get("/health/provider").json()
    assert body["serp_provider"] == "serper"
    assert body["serp_configured"] is False
    assert body["volume_provider"] == "none"


def test_cache_only_rescores_an_expired_page_without_spending(monkeypatch):
    import store

    stale = {"keyword": "old page", "provider": "serpapi", "keyword_data": {}, "items": [{"type": "organic"}] * 5}
    store.save_snapshot("old page", "United States", "English", False, stale, fetched_at="2020-01-01T00:00:00+00:00")
    monkeypatch.setenv("SERP_PROVIDER", "serpapi")  # no key: any provider call would fail with 503

    body = client.post("/analyze", json={"keyword": "old page", "search_volume": 2000, "cache_only": True}).json()
    assert body["source"] == "cache" and body["raw_volume"] == 2000
    assert usage.calls_today() == 0
    missing = client.post("/analyze", json={"keyword": "never analyzed", "cache_only": True})
    assert missing.status_code == 409
