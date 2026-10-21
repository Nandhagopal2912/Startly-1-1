from collections import Counter

import pytest
from fastapi import HTTPException

from conftest import load_fixture

import usage
from providers import get_serp_provider
from providers.serper import SerperProvider, normalize


def test_serper_normalize_maps_serp_features():
    snapshot = normalize(load_fixture("serper_best_crm.json"), "best crm software")
    types = Counter(item["type"] for item in snapshot["items"])

    assert snapshot["provider"] == "serper"
    assert snapshot["keyword_data"] == {}
    assert types == {
        "organic": 7,
        "paid": 2,
        "featured_snippet": 1,
        "knowledge_graph": 1,
        "people_also_ask": 1,
    }
    domains = {item["domain"] for item in snapshot["items"] if item["type"] == "organic"}
    assert "example-reviews.com" in domains  # www. stripped


def test_serper_answer_without_link_is_answer_box():
    snapshot = normalize({"answerBox": {"answer": "42"}}, "q")
    assert snapshot["items"][0]["type"] == "answer_box"


def test_serper_without_key_fails_before_spending():
    with pytest.raises(HTTPException) as exc:
        SerperProvider().fetch_serp("crm", "United States", "English")
    assert exc.value.status_code == 503
    assert usage.calls_today() == 0


def test_unknown_provider_name_is_rejected():
    with pytest.raises(HTTPException):
        get_serp_provider("bing")


def test_daily_cap_blocks_extra_calls(monkeypatch):
    monkeypatch.setenv("MAX_API_CALLS_PER_DAY", "2")
    usage.record_call("serper", "search", "a")
    usage.record_call("serper", "search", "b")
    with pytest.raises(HTTPException) as exc:
        usage.record_call("serper", "search", "c")
    assert exc.value.status_code == 429
    assert usage.calls_today() == 2
