from collections import Counter

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from conftest import load_fixture

import providers.serpapi as serpapi
import usage
from main import app
from providers.serpapi import SerpApiProvider, normalize


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.ok = status_code < 400

    def json(self):
        return self._data


def test_normalize_detects_ai_overview_and_features():
    snapshot = normalize(load_fixture("serpapi_roth_ira.json"), "what is a roth ira")
    types = Counter(item["type"] for item in snapshot["items"])

    assert snapshot["provider"] == "serpapi"
    assert types == {"ai_overview": 1, "paid": 1, "people_also_ask": 1, "organic": 8}
    domains = [i["domain"] for i in snapshot["items"] if i["type"] == "organic"]
    assert domains[0] == "irs.gov"


def test_lazy_loaded_overview_with_only_page_token_still_counts():
    snapshot = normalize({"ai_overview": {"page_token": "abc"}, "organic_results": []}, "q")
    assert [i["type"] for i in snapshot["items"]] == ["ai_overview"]


def test_no_ai_overview_when_key_absent():
    snapshot = normalize({"organic_results": [{"position": 1, "link": "https://a.com"}]}, "q")
    assert all(i["type"] != "ai_overview" for i in snapshot["items"])


def test_missing_key_fails_before_spending():
    with pytest.raises(HTTPException) as exc:
        SerpApiProvider().fetch_serp("q", "United States", "English")
    assert exc.value.status_code == 503
    assert usage.calls_today() == 0


def test_api_error_is_reported_without_leaking_key(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "secret-key")
    monkeypatch.setattr(serpapi.requests, "get", lambda *a, **k: FakeResponse({"error": "Invalid API key."}, 401))
    with pytest.raises(HTTPException) as exc:
        SerpApiProvider().fetch_serp("q", "United States", "English")
    assert "Invalid API key" in exc.value.detail
    assert "secret-key" not in exc.value.detail


def test_empty_results_are_not_an_error(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "k")
    monkeypatch.setattr(
        serpapi.requests, "get",
        lambda *a, **k: FakeResponse({"error": "Google hasn't returned any results for this query."}),
    )
    assert SerpApiProvider().fetch_serp("zzqx", "United States", "English")["items"] == []


def test_end_to_end_ai_overview_gets_zero_click_penalty(monkeypatch):
    monkeypatch.setenv("SERP_PROVIDER", "serpapi")
    monkeypatch.setenv("SERPAPI_API_KEY", "k")
    sent = []

    def fake_get(url, params, timeout):
        sent.append(params)
        return FakeResponse(load_fixture("serpapi_roth_ira.json"))

    monkeypatch.setattr(serpapi.requests, "get", fake_get)

    body = TestClient(app).post("/analyze", json={"keyword": "what is a roth ira", "search_volume": 10000}).json()
    assert body["provider"] == "serpapi"
    assert body["report"]["summary"]["penalty_percent"] == 45
    assert body["adjusted_volume"] == 5500
    assert "Zero-Click Search Risk" in [s["title"] for s in body["report"]["sections"]]
    assert sent[0]["engine"] == "google" and sent[0]["gl"] == "us"
    assert usage.calls_today() == 1
