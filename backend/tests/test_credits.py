from fastapi.testclient import TestClient

import providers.serpapi as serpapi
import usage
from main import app

client = TestClient(app)
SERPAPI_KEY, SERPER_KEY = "serpapiownerkey1234567890", "serperownerkey1234567890"


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data, self.status_code, self.ok = data, status_code, status_code < 400

    def json(self):
        return self._data


def fake_accounts(monkeypatch, calls, serpapi_data=None, serper_data=None, serper_status=200):
    """Both provider modules share the requests library, so one fake answers by URL."""
    def fake_get(url, params=None, headers=None, timeout=None):
        if "serpapi.com" in url:
            calls.append("serpapi")
            return FakeResponse(serpapi_data or {"plan_name": "Free Plan", "searches_per_month": 250, "total_searches_left": 247,
                                                 "account_email": "owner@example.com", "api_key": SERPAPI_KEY})
        calls.append("serper")
        return FakeResponse(serper_data if serper_data is not None else {"balance": 2495, "rateLimit": 5}, serper_status)

    monkeypatch.setattr(serpapi.requests, "get", fake_get)


def by_name(body):
    return {p["provider"]: p for p in body["providers"]}


def test_shows_credits_for_both_server_keys_without_revealing_them(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", SERPAPI_KEY)
    monkeypatch.setenv("SERPER_API_KEY", SERPER_KEY)
    monkeypatch.setenv("SERP_PROVIDER", "serpapi")
    fake_accounts(monkeypatch, [])
    usage.record_call("serpapi", "search", "kw")

    res = client.get("/credits")
    body = by_name(res.json())
    assert body["serpapi"]["credits_left"] == 247 and body["serpapi"]["plan"] == "Free Plan"
    assert body["serpapi"]["credits_per_month"] == 250 and body["serpapi"]["active"] is True
    assert body["serpapi"]["used_today"] == 1
    assert body["serper"]["credits_left"] == 2495 and body["serper"]["active"] is False
    assert res.json()["calls_today"] == 1 and res.json()["daily_cap"] == 50
    text = res.text
    assert SERPAPI_KEY not in text and SERPER_KEY not in text and "owner@example.com" not in text


def test_missing_keys_are_reported_without_calls(monkeypatch):
    calls = []
    fake_accounts(monkeypatch, calls)
    body = by_name(client.get("/credits").json())
    assert body["serpapi"]["configured"] is False and body["serper"]["configured"] is False
    assert calls == []


def test_one_failing_provider_does_not_hide_the_other(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", SERPAPI_KEY)
    monkeypatch.setenv("SERPER_API_KEY", SERPER_KEY)
    fake_accounts(monkeypatch, [], serper_data={"message": "Unauthorized."}, serper_status=403)
    body = by_name(client.get("/credits").json())
    assert body["serpapi"]["credits_left"] == 247
    assert body["serper"]["credits_left"] is None and "serper.dev/dashboard" in body["serper"]["error"]


def test_results_are_cached_for_a_minute_unless_refreshed(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", SERPER_KEY)
    calls = []
    fake_accounts(monkeypatch, calls)
    client.get("/credits")
    client.get("/credits")
    assert calls == ["serper"]
    client.get("/credits", params={"refresh": True})
    assert calls == ["serper", "serper"]


def test_demo_mode_hides_owner_balances(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("SERPAPI_API_KEY", SERPAPI_KEY)
    calls = []
    fake_accounts(monkeypatch, calls)
    assert client.get("/credits").json() == {"demo": True, "providers": []}
    assert calls == []
