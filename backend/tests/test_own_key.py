import json

from fastapi.testclient import TestClient

from conftest import load_fixture

import providers.serpapi as serpapi
import usage
from db import connect
from main import app

client = TestClient(app)
KEY = "abc123visitorkey456def789"
HEADERS = {"X-SerpApi-Key": KEY}


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data, self.status_code, self.ok = data, status_code, status_code < 400

    def json(self):
        return self._data


def counts():
    with connect() as conn:
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("analyses", "serp_snapshots", "keyword_volume")}


def fake_serpapi(monkeypatch, sent, data=None):
    def fake_get(url, params, timeout):
        sent.append(params)
        return FakeResponse(data if data is not None else load_fixture("serpapi_roth_ira.json"))

    monkeypatch.setattr(serpapi.requests, "get", fake_get)


def test_own_key_search_uses_that_key_and_stores_nothing(monkeypatch):
    sent = []
    fake_serpapi(monkeypatch, sent)
    before = counts()

    body = client.post("/analyze", headers=HEADERS, json={"keyword": "what is a roth ira", "search_volume": 10000}).json()

    assert sent[0]["api_key"] == KEY
    assert body["own_key"] is True and body["analysis_id"] is None
    assert body["capturable_clicks"] > 0 and body["report"]["verdict"]["label"]
    assert body["snapshot"]["items"] and body["snapshot_fetched_at"]
    assert body["changes"]["has_previous"] is False
    assert counts() == before
    assert usage.calls_today() == 0  # the visitor's quota, not the server's cap
    assert KEY not in json.dumps(body)


def test_own_key_works_in_demo_mode_for_any_keyword(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    sent = []
    fake_serpapi(monkeypatch, sent)
    assert client.post("/analyze", json={"keyword": "brand new keyword"}).status_code == 404
    ok = client.post("/analyze", headers=HEADERS, json={"keyword": "brand new keyword"})
    assert ok.status_code == 200 and len(sent) == 1


def test_recheck_compares_with_previous_check_sent_by_browser(monkeypatch):
    sent = []
    fake_serpapi(monkeypatch, sent)
    older = {"keyword": "what is a roth ira", "provider": "serpapi",
             "items": [{"type": "organic", "domain": f"site{i}.com", "rank_group": i} for i in range(1, 9)]}
    body = client.post("/analyze", headers=HEADERS, json={
        "keyword": "what is a roth ira", "search_volume": 10000,
        "previous": {"snapshot": older, "fetched_at": "2026-10-01T00:00:00+00:00"},
    }).json()
    changes = body["changes"]
    assert changes["has_previous"] and changes["previous_fetched_at"] == "2026-10-01T00:00:00+00:00"
    assert "AI Overview" in {f["label"] for f in changes["features_added"]}
    assert changes["clicks_after"] < changes["clicks_before"]


def test_malformed_key_is_rejected_before_any_search(monkeypatch):
    sent = []
    fake_serpapi(monkeypatch, sent)
    for bad in ["short", "has spaces in it 123456789", "x" * 129, "semi;colon1234567890123"]:
        res = client.post("/analyze", headers={"X-SerpApi-Key": bad}, json={"keyword": "kw"})
        assert res.status_code == 400, bad
    assert sent == []


def test_provider_errors_never_echo_the_key(monkeypatch):
    sent = []
    fake_serpapi(monkeypatch, sent, data={"error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"})
    res = client.post("/analyze", headers=HEADERS, json={"keyword": "kw"})
    assert res.status_code == 502 and KEY not in res.text


def test_rescore_changes_volume_without_any_search(monkeypatch):
    sent = []
    fake_serpapi(monkeypatch, sent)
    first = client.post("/analyze", headers=HEADERS, json={"keyword": "what is a roth ira", "search_volume": 10000}).json()

    rescored = client.post("/rescore", json={
        "keyword": "what is a roth ira", "search_volume": 5000,
        "snapshot": first["snapshot"], "snapshot_fetched_at": first["snapshot_fetched_at"],
    }).json()

    assert len(sent) == 1  # only the original search
    assert rescored["source"] == "browser" and rescored["raw_volume"] == 5000
    assert abs(rescored["capturable_clicks"] - first["capturable_clicks"] / 2) <= 1
    assert rescored["analyzed_at"] == first["snapshot_fetched_at"]


def test_rescore_rejects_oversized_or_malformed_pages():
    huge = {"items": [{"type": "organic"}] * 101}
    assert client.post("/rescore", json={"keyword": "k", "snapshot": huge, "snapshot_fetched_at": "x"}).status_code == 422
    bad_type = {"items": [{"type": "x" * 51}]}
    assert client.post("/rescore", json={"keyword": "k", "snapshot": bad_type, "snapshot_fetched_at": "x"}).status_code == 422


def test_key_check_returns_plan_only(monkeypatch):
    monkeypatch.setattr(serpapi.requests, "get", lambda url, params, timeout: FakeResponse({
        "account_email": "visitor@example.com", "api_key": KEY, "account_id": "42",
        "plan_name": "Free Plan", "searches_per_month": 250, "total_searches_left": 249,
    }))
    body = client.post("/key/check", headers=HEADERS).json()
    assert body == {"valid": True, "plan_name": "Free Plan", "searches_per_month": 250, "searches_left": 249}


def test_key_check_rejects_bad_or_missing_keys(monkeypatch):
    monkeypatch.setattr(serpapi.requests, "get", lambda url, params, timeout: FakeResponse({"error": "Invalid API key."}, 401))
    assert client.post("/key/check", headers=HEADERS).status_code == 400
    assert client.post("/key/check").status_code == 400


def test_bulk_with_own_key_searches_each_keyword_and_stores_nothing(monkeypatch):
    sent = []
    fake_serpapi(monkeypatch, sent)
    before = counts()
    body = {"keywords": [{"keyword": "a kw", "search_volume": 1000}, {"keyword": "b kw"}, {"keyword": "A KW"}]}

    preview = client.post("/bulk/preview", headers=HEADERS, json=body).json()
    assert preview == {"own_key": True, "total": 2, "new_calls": 2, "duplicates_removed": 1}

    result = client.post("/bulk/analyze", headers=HEADERS, json=body).json()
    assert len(sent) == 2 and all(p["api_key"] == KEY for p in sent)
    assert result["analyzed"] == 2 and result["own_key_searches"] == 2 and result["api_calls_used"] == 0
    assert all(r["analysis"]["snapshot"] for r in result["results"])
    assert counts() == before


def test_cors_allows_the_key_header():
    res = client.options("/analyze", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-serpapi-key",
    })
    assert res.status_code == 200
    assert "x-serpapi-key" in res.headers.get("access-control-allow-headers", "").lower()
