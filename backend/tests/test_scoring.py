from conftest import load_fixture

from providers.dataforseo import normalize_serp
from providers.mock import MockProvider
from scoring import analyze_payload, penalty_percent


def test_penalty_tiers():
    assert penalty_percent([]) == 0
    assert penalty_percent(["people_also_ask", "ai_overview"]) == 45
    assert penalty_percent(["paid", "video"]) == 35
    assert penalty_percent(["shopping"]) == 35
    assert penalty_percent(["people_also_ask", "video"]) == 20


def test_dataforseo_paid_ads_count_as_commercial():
    snapshot = normalize_serp(load_fixture("dataforseo_serp.json"), "running shoes")
    result = analyze_payload(snapshot, "running shoes", volume_override=1000)

    summary = result["report"]["summary"]
    assert result["organic_results"] == 5
    assert result["total_results"] == 8
    assert summary["penalty_percent"] == 35
    assert result["adjusted_volume"] == 650
    titles = [s["title"] for s in result["report"]["sections"]]
    assert "Competitive Commercial Intent" in titles


def test_top_level_adjusted_volume_matches_report():
    snapshot = MockProvider().fetch_serp("crm", "United States", "English")
    result = analyze_payload(snapshot, "crm")
    assert result["adjusted_volume"] == result["report"]["summary"]["adjusted_volume"]
    assert result["volume_source"] == "mock"


def test_volume_override_wins_and_unknown_volume_is_labelled():
    snapshot = {"keyword": "x", "provider": "serper", "keyword_data": {}, "items": [{"type": "organic"}]}
    assert analyze_payload(snapshot, "x")["volume_source"] == "unknown"
    overridden = analyze_payload(snapshot, "x", volume_override=500)
    assert overridden["raw_volume"] == 500
    assert overridden["volume_source"] == "user"


def test_no_organic_results_does_not_crash():
    snapshot = {"keyword": "x", "keyword_data": {}, "items": [{"type": "ai_overview"}, {"type": "paid"}]}
    result = analyze_payload(snapshot, "x", volume_override=100)
    assert result["report"]["summary"]["demand_per_organic_slot"] is None
    assert "No classic organic listings" in result["report"]["sections"][-1]["body"]


def test_legacy_cached_dataforseo_payload_still_parses():
    legacy = load_fixture("dataforseo_serp.json")
    legacy["tasks"][0]["result"][0]["keyword_data"] = {"search_volume": 2000}
    result = analyze_payload(legacy, "running shoes")
    assert result["raw_volume"] == 2000
    assert result["organic_results"] == 5
