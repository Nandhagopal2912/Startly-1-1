import pytest

from conftest import load_fixture

from providers.dataforseo import normalize_serp
from providers.mock import MockProvider
from scoring import analyze_payload


def snap(*types):
    return {"keyword": "x", "provider": "serper", "keyword_data": {}, "items": [{"type": t} for t in types]}


def titles(result):
    return [s["title"] for s in result["report"]["sections"]]


def test_dataforseo_ads_reduce_position_1_and_flag_low_confidence():
    """running shoes: 1 ad, shopping, PAA, 5 organic results."""
    snapshot = normalize_serp(load_fixture("dataforseo_serp.json"), "running shoes")
    result = analyze_payload(snapshot, "running shoes", volume_override=1000)
    summary = result["report"]["summary"]

    assert result["organic_results"] == 5
    assert result["total_results"] == 8
    # Positions 1-5 = 41.6% on a plain page; the ad cuts #1 from 19.38% to 13.57% -> 35.79% total.
    assert result["capturable_clicks"] == 358
    assert result["capturable_clicks_low"] == result["capturable_clicks_high"] == 358  # one costly feature, no overlap
    assert summary["penalty_percent"] == 14
    assert "Competitive Commercial Intent" in titles(result)
    assert "Model Confidence" in titles(result)


def test_adjusted_volume_is_capturable_clicks():
    snapshot = MockProvider().fetch_serp("crm", "United States", "English")
    result = analyze_payload(snapshot, "crm")
    assert result["volume_source"] == "mock"
    assert result["adjusted_volume"] == result["capturable_clicks"] == result["report"]["summary"]["adjusted_volume"]


def test_ai_overview_triggers_zero_click_section_with_measured_effect():
    result = analyze_payload(snap("ai_overview", *["organic"] * 8), "x", volume_override=10000)
    zero_click = next(s for s in result["report"]["sections"] if s["title"] == "Zero-Click Search Risk")
    assert "AI Overview -52% at #1" in zero_click["body"]
    assert result["penalty_applied"] is True


def test_people_also_ask_and_video_cost_nothing():
    plain = analyze_payload(snap(*["organic"] * 8), "x", volume_override=10000)
    rich = analyze_payload(snap("people_also_ask", "video", *["organic"] * 8), "x", volume_override=10000)
    assert rich["capturable_clicks"] == plain["capturable_clicks"]
    assert rich["report"]["summary"]["penalty_percent"] == 0
    assert "don't measurably lower organic clicks" in rich["report"]["sections"][1]["body"]


def test_range_and_value_by_position_text():
    result = analyze_payload(snap("ai_overview", "paid", "images", *["organic"] * 6), "x", volume_override=10000)
    demand = result["report"]["sections"][0]["body"]
    assert "range" in demand
    value = next(s for s in result["report"]["sections"] if s["title"] == "Value by Position")
    assert value["body"].startswith("Estimated monthly clicks by ranking: #1 ~")
    assert "#6 ~" in value["body"]


def test_unknown_volume_reports_ctr_instead_of_clicks():
    result = analyze_payload(snap("ai_overview", *["organic"] * 5), "x")
    assert result["volume_source"] == "unknown"
    assert result["capturable_clicks"] is None
    assert result["adjusted_volume"] == 0
    assert "Enter a monthly search volume" in result["report"]["sections"][0]["body"]
    assert "%" in next(s for s in result["report"]["sections"] if s["title"] == "Value by Position")["body"]


def test_verdict_uses_top_three_clicks():
    big = analyze_payload(snap(*["organic"] * 10), "x", volume_override=10000)
    small = analyze_payload(snap(*["organic"] * 10), "x", volume_override=500)
    assert "worth targeting" in big["report"]["sections"][-1]["body"]
    assert "modest traffic" in small["report"]["sections"][-1]["body"]


def test_no_organic_results_does_not_crash():
    result = analyze_payload(snap("ai_overview", "paid"), "x", volume_override=100)
    assert result["capturable_clicks"] == 0
    assert result["report"]["summary"]["demand_per_organic_slot"] is None
    assert "No classic organic listings" in result["report"]["sections"][-1]["body"]


def test_volume_override_wins_and_unknown_volume_is_labelled():
    assert analyze_payload(snap("organic"), "x")["volume_source"] == "unknown"
    overridden = analyze_payload(snap("organic"), "x", volume_override=500)
    assert overridden["raw_volume"] == 500
    assert overridden["volume_source"] == "user"


def test_legacy_cached_dataforseo_payload_still_parses():
    legacy = load_fixture("dataforseo_serp.json")
    legacy["tasks"][0]["result"][0]["keyword_data"] = {"search_volume": 2000}
    result = analyze_payload(legacy, "running shoes")
    assert result["raw_volume"] == 2000
    assert result["capturable_clicks"] == pytest.approx(716, abs=1)
