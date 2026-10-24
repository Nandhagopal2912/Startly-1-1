from fastapi.testclient import TestClient

from conftest import load_fixture

import providers.serpapi as serpapi
import store
import usage
from main import app

client = TestClient(app)


class FakeResponse:
    status_code, ok, text = 200, True, ""

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def fake_both(monkeypatch, calls):
    """SerpApi uses requests.get and Serper requests.post (both through the shared requests module)."""
    monkeypatch.setenv("SERPAPI_API_KEY", "serpapikey1234567890abc")
    monkeypatch.setenv("SERPER_API_KEY", "serperkey1234567890abc")

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append("serpapi")
        return FakeResponse(load_fixture("serpapi_roth_ira.json"))

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append("serper")
        return FakeResponse(load_fixture("serper_best_crm.json"))

    monkeypatch.setattr(serpapi.requests, "get", fake_get)
    monkeypatch.setattr(serpapi.requests, "post", fake_post)


def test_chosen_provider_overrides_the_default(monkeypatch):
    calls = []
    fake_both(monkeypatch, calls)
    monkeypatch.setenv("SERP_PROVIDER", "serpapi")

    chosen = client.post("/analyze", json={"keyword": "kw one", "provider": "serper"}).json()
    default = client.post("/analyze", json={"keyword": "kw two"}).json()

    assert calls == ["serper", "serpapi"]
    assert chosen["provider"] == "serper" and default["provider"] == "serpapi"
    assert usage.calls_by_provider_today() == {"serper": 1, "serpapi": 1}


def test_recheck_uses_the_chosen_provider(monkeypatch):
    calls = []
    fake_both(monkeypatch, calls)
    monkeypatch.setenv("SERP_PROVIDER", "serpapi")
    client.post("/analyze", json={"keyword": "kw"})
    rechecked = client.post("/analyze", json={"keyword": "kw", "refresh": True, "provider": "serper"}).json()
    assert calls == ["serpapi", "serper"] and rechecked["provider"] == "serper"
    assert rechecked["changes"]["has_previous"] is True  # compared across providers


def test_cached_keyword_keeps_its_source_until_rechecked(monkeypatch):
    calls = []
    fake_both(monkeypatch, calls)
    client.post("/analyze", json={"keyword": "kw", "provider": "serpapi"})
    again = client.post("/analyze", json={"keyword": "kw", "provider": "serper"}).json()
    assert calls == ["serpapi"] and again["source"] == "cache" and again["provider"] == "serpapi"


def test_bulk_uses_the_chosen_provider(monkeypatch):
    calls = []
    fake_both(monkeypatch, calls)
    monkeypatch.setenv("SERP_PROVIDER", "serpapi")
    body = client.post("/bulk/analyze", json={"provider": "serper", "keywords": [{"keyword": "a"}, {"keyword": "b"}]}).json()
    assert calls == ["serper", "serper"]
    assert {r["analysis"]["provider"] for r in body["results"]} == {"serper"}


def test_unknown_provider_is_rejected():
    assert client.post("/analyze", json={"keyword": "kw", "provider": "bing"}).status_code == 422


def test_chosen_provider_without_a_key_explains_what_is_missing(monkeypatch):
    monkeypatch.setenv("SERP_PROVIDER", "serpapi")
    res = client.post("/analyze", json={"keyword": "kw", "provider": "serper"})
    assert res.status_code == 503 and "SERPER_API_KEY" in res.json()["detail"]


def test_demo_mode_ignores_the_choice(monkeypatch):
    calls = []
    fake_both(monkeypatch, calls)
    monkeypatch.setenv("DEMO_MODE", "true")
    store.save_snapshot("kw", "United States", "English", False,
                        {"keyword": "kw", "provider": "serpapi", "keyword_data": {}, "items": [{"type": "organic"}]})
    body = client.post("/analyze", json={"keyword": "kw", "provider": "serper"}).json()
    assert body["provider"] == "serpapi" and calls == []
