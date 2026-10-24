from fastapi.testclient import TestClient

import store
import usage
from db import connect
from main import MAX_REPORT_ROWS, app

client = TestClient(app)
PAGE = {"keyword": "x", "provider": "serpapi", "keyword_data": {}, "items": [{"type": "ai_overview"}] + [{"type": "organic", "domain": f"s{i}.com", "rank_group": i} for i in range(1, 7)]}


def count(table):
    with connect() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def seed_demo_keyword(keyword="what is a roth ira", volume=10000):
    store.save_snapshot(keyword, "United States", "English", False, PAGE, fetched_at="2020-01-01T00:00:00+00:00")
    store.save_volume(keyword, "United States", "English", volume, "user")


# --- demo mode ---

def test_demo_serves_saved_pages_of_any_age_without_writing(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("SERP_PROVIDER", "serpapi")  # no key: a provider call would fail
    seed_demo_keyword()
    before = (count("analyses"), count("serp_snapshots"), count("keyword_volume"))

    body = client.post("/analyze", json={"keyword": "What is a Roth IRA"}).json()
    assert body["demo"] is True and body["analysis_id"] is None
    assert body["raw_volume"] == 10000 and body["capturable_clicks"] > 0
    assert body["report"]["verdict"]["label"]

    edited = client.post("/analyze", json={"keyword": "what is a roth ira", "search_volume": 500}).json()
    assert edited["raw_volume"] == 500
    assert store.get_volume("what is a roth ira", "United States", "English") == (10000.0, "user")  # not saved

    assert (count("analyses"), count("serp_snapshots"), count("keyword_volume")) == before
    assert usage.calls_today() == 0


def test_demo_rejects_unknown_keywords_rechecks_and_mock(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    seed_demo_keyword()
    unknown = client.post("/analyze", json={"keyword": "brand new keyword"})
    assert unknown.status_code == 404 and "isn't in the demo" in unknown.json()["detail"]
    assert client.post("/analyze", json={"keyword": "what is a roth ira", "refresh": True}).status_code == 403
    assert client.post("/analyze", json={"keyword": "anything", "mock_mode": True}).status_code == 403
    assert count("serp_snapshots") == 1


def test_demo_bulk_reports_unavailable_keywords_and_spends_nothing(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    seed_demo_keyword()
    body = {"keywords": [{"keyword": "what is a roth ira"}, {"keyword": "not saved"}]}

    preview = client.post("/bulk/preview", json=body).json()
    assert preview["demo"] is True and preview["new_calls"] == 0 and preview["unavailable"] == 1

    result = client.post("/bulk/analyze", json=body).json()
    assert result["analyzed"] == 1 and result["errors"] == 1 and result["api_calls_used"] == 0
    assert count("analyses") == 0


def test_demo_keyword_list_only_exists_in_demo(monkeypatch):
    seed_demo_keyword()
    assert client.get("/demo/keywords").status_code == 404
    monkeypatch.setenv("DEMO_MODE", "true")
    keywords = client.get("/demo/keywords").json()
    assert keywords == [{"keyword": "what is a roth ira", "location": "United States", "fetched_at": "2020-01-01T00:00:00+00:00"}]
    assert client.get("/health/provider").json()["demo_mode"] is True


# --- CORS ---

def test_cors_allows_only_configured_origins():
    ok = client.options("/analyze", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.options("/analyze", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


def test_local_development_allows_any_localhost_port():
    for origin in ["http://localhost:3001", "http://127.0.0.1:5173"]:
        res = client.options("/analyze", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
        assert res.headers.get("access-control-allow-origin") == origin, origin
    for origin in ["http://localhost.evil.example", "https://localhost:3000.evil.example", "http://192.168.1.5:3000"]:
        res = client.options("/analyze", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
        assert "access-control-allow-origin" not in res.headers, origin


def test_setting_allowed_origins_turns_off_the_localhost_rule(monkeypatch):
    import config

    monkeypatch.setenv("ALLOWED_ORIGINS", "https://startly.example")
    assert config.allowed_origin_regex() is None


def test_allowed_origins_come_from_env(monkeypatch):
    import config

    monkeypatch.setenv("ALLOWED_ORIGINS", "https://startly.example/, https://www.startly.example")
    assert config.allowed_origins() == ["https://startly.example", "https://www.startly.example"]


# --- rate limiting ---

def test_rate_limit_returns_429_with_retry_after(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    assert [client.get("/health").status_code for _ in range(3)] == [200, 200, 200]
    blocked = client.get("/health")
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1
    assert "Too many requests" in blocked.json()["detail"]


def test_rate_limit_is_per_forwarded_ip_behind_a_proxy(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    assert client.get("/health", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert client.get("/health", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
    assert client.get("/health", headers={"X-Forwarded-For": "1.1.1.1, 10.0.0.1"}).status_code == 429


def test_forwarded_header_is_ignored_unless_trusted(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    assert client.get("/health", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    # Spoofing a different address doesn't get a fresh allowance.
    assert client.get("/health", headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 429


# --- input limits and error messages ---

def test_oversized_inputs_are_rejected():
    assert client.post("/analyze", json={"keyword": "k" * 201, "mock_mode": True}).status_code == 422
    rows = [{"keyword": f"k{i}"} for i in range(MAX_REPORT_ROWS + 1)]
    assert client.post("/report", json={"rows": rows, "format": "csv"}).status_code == 422


def test_errors_do_not_reveal_server_paths(monkeypatch):
    monkeypatch.setenv("SERP_PROVIDER", "dataforseo")
    detail = client.post("/analyze", json={"keyword": "anything"}).json()["detail"]
    assert "backend/.env" in detail
    assert ":\\" not in detail and "/home/" not in detail and "Projects" not in detail
