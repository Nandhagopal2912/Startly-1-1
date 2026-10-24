from fastapi.testclient import TestClient

import store
import usage
from db import connect
from main import app

client = TestClient(app)


def analyze(keyword, volume=None):
    body = {"keyword": keyword, "mock_mode": True}
    if volume is not None:
        body["search_volume"] = volume
    return client.post("/analyze", json=body).json()


def test_analyze_returns_id_and_timestamp():
    result = analyze("crm", 5000)
    assert isinstance(result["analysis_id"], int)
    assert result["analyzed_at"].endswith("+00:00")


def test_history_item_reopens_exact_result():
    original = analyze("crm", 5000)
    reopened = client.get(f"/history/{original['analysis_id']}").json()
    assert reopened == original
    assert reopened["report"]["click_model"]["positions"]


def test_reopening_does_not_record_or_spend():
    original = analyze("crm", 5000)
    client.get(f"/history/{original['analysis_id']}")
    client.get("/history/latest")
    assert len(client.get("/history").json()) == 1
    assert usage.calls_today() == 0


def test_missing_history_item_is_404():
    assert client.get("/history/999").status_code == 404


def test_latest_keeps_newest_per_keyword_newest_first():
    analyze("alpha", 100)
    analyze("beta", 200)
    newer_alpha = analyze("Alpha", 300)  # same keyword, different case

    latest = client.get("/history/latest").json()
    assert [r["keyword"].lower() for r in latest] == ["alpha", "beta"]
    assert latest[0]["analysis_id"] == newer_alpha["analysis_id"]
    assert latest[0]["raw_volume"] == 300


def test_latest_after_id_skips_cleared_analyses():
    first = analyze("old one", 100)
    analyze("new one", 200)
    latest = client.get("/history/latest", params={"after_id": first["analysis_id"]}).json()
    assert [r["keyword"] for r in latest] == ["new one"]


def test_history_search_and_paging():
    for kw in ["crm software", "best crm", "email tools", "Free CRM"]:
        analyze(kw, 100)
    found = client.get("/history", params={"q": "crm"}).json()
    assert sorted(r["keyword"] for r in found) == ["Free CRM", "best crm", "crm software"]
    assert all("id" in r and r["exact"] is True for r in found)

    page1 = client.get("/history", params={"limit": 2}).json()
    page2 = client.get("/history", params={"limit": 2, "offset": 2}).json()
    assert len(page1) == 2 and len(page2) == 2
    assert not {r["id"] for r in page1} & {r["id"] for r in page2}


def test_search_treats_wildcards_literally():
    analyze("100% organic", 10)
    analyze("1000 organic", 10)
    assert [r["keyword"] for r in client.get("/history", params={"q": "100%"}).json()] == ["100% organic"]


def test_legacy_analysis_without_stored_result_is_rescored():
    original = analyze("legacy kw", 4000)
    with connect() as conn:
        conn.execute("UPDATE analyses SET result = NULL WHERE id = ?", (original["analysis_id"],))

    assert client.get("/history").json()[0]["exact"] is False
    reopened = client.get(f"/history/{original['analysis_id']}").json()
    assert reopened["source"] == "history" and reopened["rescored"] is True
    assert reopened["raw_volume"] == 4000
    assert reopened["capturable_clicks"] == original["capturable_clicks"]


def test_legacy_analysis_without_snapshot_is_skipped():
    original = analyze("orphan", 100)
    with connect() as conn:
        conn.execute("UPDATE analyses SET result = NULL, snapshot_id = NULL WHERE id = ?", (original["analysis_id"],))
    assert client.get(f"/history/{original['analysis_id']}").status_code == 404
    assert store.latest_analysis_ids() == [original["analysis_id"]]
    assert client.get("/history/latest").json() == []
