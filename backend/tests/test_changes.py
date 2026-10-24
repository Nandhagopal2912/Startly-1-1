from fastapi.testclient import TestClient

from conftest import load_fixture

import providers.serpapi as serpapi
import store
import usage
from changes import diff_snapshots
from db import connect
from main import app

client = TestClient(app)


def snap(*items):
    return {"keyword": "kw", "provider": "serpapi", "keyword_data": {}, "items": list(items)}


def org(domain, rank):
    return {"type": "organic", "domain": domain, "rank_group": rank}


BEFORE = snap({"type": "paid"}, org("a.com", 1), org("b.com", 2), org("c.com", 3), org("d.com", 4))
AFTER = snap(
    {"type": "ai_overview"}, {"type": "paid"}, {"type": "paid"}, {"type": "paid"},
    org("c.com", 1), org("a.com", 2), org("e.com", 3), org("b.com", 4),
)


def test_diff_finds_features_counts_and_domain_moves():
    d = diff_snapshots(BEFORE, AFTER, "kw", volume=10000)

    assert d["has_changes"] is True
    assert [f["label"] for f in d["features_added"]] == ["AI Overview"]
    assert d["feature_counts_changed"] == [{"type": "paid", "label": "Top ads", "before": 1, "after": 3}]
    assert d["domains_entered"] == [{"domain": "e.com", "position": 3}]
    assert d["domains_left"] == [{"domain": "d.com", "position": 4}]
    assert {(m["domain"], m["before"], m["after"]) for m in d["domains_moved"]} == {
        ("c.com", 3, 1), ("a.com", 1, 2), ("b.com", 2, 4),
    }
    assert d["clicks_after"] < d["clicks_before"]
    assert d["click_loss_after"] > d["click_loss_before"]
    summary = " ".join(d["summary"])
    assert "AI Overview appeared." in summary
    assert "Top ads: 1 → 3." in summary
    assert "Capturable clicks:" in summary and "%)" in summary
    assert "New on page one: e.com (#3)." in summary
    assert "Dropped off page one: d.com (was #4)." in summary


def test_diff_of_identical_pages_reports_no_changes():
    d = diff_snapshots(BEFORE, BEFORE, "kw", volume=500)
    assert d["has_changes"] is False
    assert d["summary"] == ["No changes since the previous check."]


def test_diff_without_volume_compares_click_through():
    d = diff_snapshots(BEFORE, AFTER, "kw")
    assert d["clicks_before"] is None
    assert any(s.startswith("Organic click-through:") for s in d["summary"])


def test_feature_removal_is_reported():
    d = diff_snapshots(AFTER, BEFORE, "kw", volume=1000)
    assert [f["label"] for f in d["features_removed"]] == ["AI Overview"]
    assert "AI Overview disappeared." in d["summary"]


def test_first_analysis_has_no_previous():
    result = client.post("/analyze", json={"keyword": "crm", "mock_mode": True}).json()
    assert result["changes"]["has_previous"] is False
    assert result["changes"]["current_fetched_at"]


def test_refresh_skips_cache_and_compares_with_previous():
    first = client.post("/analyze", json={"keyword": "crm", "mock_mode": True, "search_volume": 1000}).json()
    cached = client.post("/analyze", json={"keyword": "crm", "mock_mode": True}).json()
    rechecked = client.post("/analyze", json={"keyword": "crm", "mock_mode": True, "refresh": True}).json()

    assert first["source"] == "api" and cached["source"] == "cache" and rechecked["source"] == "api"
    assert cached["changes"]["has_previous"] is False  # still the first snapshot
    assert rechecked["changes"]["has_previous"] is True
    assert rechecked["changes"]["has_changes"] is False  # mock pages are deterministic
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM serp_snapshots").fetchone()[0] == 2


def test_live_recheck_spends_one_call_and_reports_real_differences(monkeypatch):
    monkeypatch.setenv("SERP_PROVIDER", "serpapi")
    monkeypatch.setenv("SERPAPI_API_KEY", "k")

    class FakeResponse:
        status_code, ok = 200, True

        def json(self):
            return load_fixture("serpapi_roth_ira.json")

    monkeypatch.setattr(serpapi.requests, "get", lambda *a, **k: FakeResponse())
    # An older check of the same keyword, before the AI Overview and ad showed up.
    older = snap(*[org(f"site{i}.com", i) for i in range(1, 9)])
    store.save_snapshot("what is a roth ira", "United States", "English", False, older, fetched_at="2026-10-01T00:00:00+00:00")

    result = client.post("/analyze", json={"keyword": "what is a roth ira", "search_volume": 10000, "refresh": True}).json()

    assert usage.calls_today() == 1
    changes = result["changes"]
    assert changes["previous_fetched_at"] == "2026-10-01T00:00:00+00:00"
    assert {f["label"] for f in changes["features_added"]} >= {"AI Overview", "Top ads"}
    assert changes["clicks_after"] < changes["clicks_before"]
    assert changes["domains_entered"][0] == {"domain": "irs.gov", "position": 1}


def test_changes_are_kept_in_history():
    client.post("/analyze", json={"keyword": "crm", "mock_mode": True})
    rechecked = client.post("/analyze", json={"keyword": "crm", "mock_mode": True, "refresh": True}).json()
    reopened = client.get(f"/history/{rechecked['analysis_id']}").json()
    assert reopened["changes"] == rechecked["changes"]
