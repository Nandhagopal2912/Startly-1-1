from conftest import load_fixture

from providers.serpapi import normalize as serpapi_normalize
from scoring import analyze_payload


def snap(*items):
    return {"keyword": "kw", "provider": "serpapi", "keyword_data": {}, "items": list(items)}


def org(domain, rank):
    return {"type": "organic", "domain": domain, "rank_group": rank}


def rec_ids(result):
    return [r["id"] for r in result["report"]["recommendations"]]


def test_page_one_lists_domains_with_position_clicks():
    snapshot = serpapi_normalize(load_fixture("serpapi_roth_ira.json"), "what is a roth ira")
    report = analyze_payload(snapshot, "what is a roth ira", volume_override=10000)["report"]
    rows = report["page_one"]
    assert [r["domain"] for r in rows[:2]] == ["irs.gov", "example-finance.com"]
    assert [r["position"] for r in rows] == list(range(1, 9))
    assert rows[0]["clicks"] == report["click_model"]["positions"][0]["clicks"]


def test_page_one_orders_by_rank():
    report = analyze_payload(snap(org("b.com", 2), org("a.com", 1)), "kw", volume_override=100)["report"]
    assert [r["domain"] for r in report["page_one"]] == ["a.com", "b.com"]


def test_verdict_tiers_follow_top_three_clicks():
    page = snap(*[org(f"s{i}.com", i) for i in range(1, 11)])
    assert analyze_payload(page, "kw", volume_override=20000)["report"]["verdict"]["label"] == "Worth targeting"
    assert analyze_payload(page, "kw", volume_override=1000)["report"]["verdict"]["label"] == "Modest opportunity"
    low = analyze_payload(page, "kw", volume_override=200)["report"]
    assert low["verdict"]["label"] == "Low traffic potential" and low["verdict"]["tone"] == "bad"
    assert "low_potential" in [r["id"] for r in low["recommendations"]]


def test_verdict_without_volume_asks_for_it_first():
    result = analyze_payload(snap(org("a.com", 1)), "kw")
    assert result["report"]["verdict"]["tone"] == "unknown"
    assert rec_ids(result)[0] == "add_volume"


def test_recommendations_follow_page_features():
    page = snap({"type": "ai_overview"}, {"type": "paid"}, {"type": "people_also_ask"}, {"type": "video"},
                *[org(f"s{i}.com", i) for i in range(1, 7)])
    result = analyze_payload(page, "kw", volume_override=10000)
    ids = rec_ids(result)
    assert ids[:2] == ["ai_overview", "long_tail"]  # AI Overview + ads remove over 50% of clicks
    assert {"commercial", "paa", "video", "confidence"} <= set(ids)
    ai = next(r for r in result["report"]["recommendations"] if r["id"] == "ai_overview")
    assert "52%" in ai["detail"]


def test_local_pack_recommendation_comes_first_among_features():
    page = snap({"type": "local_pack"}, {"type": "ai_overview"}, *[org(f"s{i}.com", i) for i in range(1, 6)])
    assert rec_ids(analyze_payload(page, "kw", volume_override=5000))[0] == "local_pack"


def test_clean_page_has_no_feature_recommendations():
    page = snap(*[org(f"s{i}.com", i) for i in range(1, 11)])
    assert rec_ids(analyze_payload(page, "kw", volume_override=20000)) == []


def test_no_organic_results():
    result = analyze_payload(snap({"type": "ai_overview"}), "kw", volume_override=100)
    assert result["report"]["verdict"]["label"] == "No organic slots"
    assert result["report"]["page_one"] == []
    assert rec_ids(result) == ["no_organic"]
