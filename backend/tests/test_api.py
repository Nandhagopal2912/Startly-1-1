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
    assert body["report"]["summary"]["penalty_percent"] == 45  # knowledge graph present
    assert body["adjusted_volume"] == 5500
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
