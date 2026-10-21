import pytest

from ctr_config import BASELINE_CTR, FEATURES, NEUTRAL_FEATURES
from ctr_model import ctr_curves, estimate_clicks


def pos1_change(features):
    low, _ = ctr_curves(1, features)
    return low[0] / BASELINE_CTR[0] - 1


def test_config_values_are_sane():
    assert BASELINE_CTR == sorted(BASELINE_CTR, reverse=True)
    for name, f in FEATURES.items():
        assert f["confidence"] in {"high", "medium", "low"}, name
        assert f["url"].startswith("https://"), name
        assert all(0 < m <= 1.5 for m in f["multipliers"]), name
    assert not set(FEATURES) & set(NEUTRAL_FEATURES)


def test_clean_serp_uses_baseline():
    result = estimate_clicks(10000, 10, ["organic"])
    assert result["organic_ctr_total"] == pytest.approx(sum(BASELINE_CTR), abs=0.01)
    assert result["capturable_clicks"] == result["capturable_clicks_low"] == result["capturable_clicks_high"]
    assert result["positions"][0]["clicks"] == 1938


# AWR, July 2026, position 1 (desktop): measured changes for single features and combinations.
@pytest.mark.parametrize(
    "features, measured",
    [
        (["ai_overview"], -0.52),
        (["local_pack"], -0.94),
        (["images"], -0.26),
        (["ai_overview", "local_pack"], -0.97),
    ],
)
def test_position_1_matches_awr_measurements(features, measured):
    assert pos1_change(features) == pytest.approx(measured, abs=0.02)


def test_neutral_features_have_no_penalty():
    assert pos1_change(["people_also_ask", "video", "knowledge_graph", "featured_snippet"]) == 0


def test_range_brackets_estimate_when_features_overlap():
    r = estimate_clicks(10000, 6, ["ai_overview", "paid", "images", "people_also_ask"])
    assert r["capturable_clicks_low"] < r["capturable_clicks"] < r["capturable_clicks_high"]
    for p in r["positions"]:
        assert p["ctr_low"] <= p["ctr"] <= p["ctr_high"]


def test_curves_never_rise_at_lower_positions():
    for features in ([], ["ai_overview"], ["ai_overview", "paid", "images"]):
        low, high = ctr_curves(10, features)
        assert low == sorted(low, reverse=True)
        assert high == sorted(high, reverse=True)


def test_devops_example():
    """devops: AI Overview, 1 ad, PAA, images, video, 6 organic results."""
    r = estimate_clicks(10000, 6, ["ai_overview", "paid", "people_also_ask", "images", "video"])
    assert r["capturable_clicks_low"] == pytest.approx(1750, abs=20)
    assert r["positions"][0]["clicks_low"] == pytest.approx(486, abs=3)
    assert r["low_confidence_factors"] == ["Top ads"]
    assert r["neutral_features"] == ["people_also_ask", "video"]


def test_organic_count_limits_positions():
    assert len(estimate_clicks(1000, 3, [])["positions"]) == 3
    assert len(estimate_clicks(1000, 25, [])["positions"]) == 10
    assert estimate_clicks(1000, 0, [])["capturable_clicks"] == 0


def test_unknown_volume_returns_ctr_only():
    r = estimate_clicks(None, 5, ["ai_overview"])
    assert r["capturable_clicks"] is None
    assert r["organic_ctr_total"] > 0
    assert r["positions"][0]["clicks"] is None


def test_aliases_map_to_features():
    assert pos1_change(["google_ads"]) == pos1_change(["paid"])
