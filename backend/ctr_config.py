"""Click-through-rate data behind Startly's click model. Every number cites its source.

Edit values here to tune the model; tests in tests/test_ctr_model.py check the results stay sane.
Percentages are the share of searches that click the organic result at that position.
"""

from __future__ import annotations

from typing import Literal, TypedDict

Confidence = Literal["high", "medium", "low"]

AWR_URL = "https://www.advancedwebranking.com/seo/organic-ctr"
AHREFS_URL = "https://ahrefs.com/blog/ai-overviews-reduce-clicks-update/"
AWR_2014_URL = "https://www.advancedwebranking.com/blog/google-organic-ctr"

# Organic CTR (%) for positions 1-10 on a results page.
# Source: Advanced Web Ranking, Google US, all devices, unbranded queries, July 2026 (1.75M+ SERPs/month).
BASELINE_CTR: list[float] = [19.38, 9.64, 6.02, 3.88, 2.68, 1.86, 1.37, 1.10, 0.94, 0.81]
BASELINE_SOURCE = {
    "name": "Advanced Web Ranking CTR study (unbranded, all devices, US, July 2026)",
    "url": AWR_URL,
}


class Feature(TypedDict):
    label: str
    # multipliers[i] scales the CTR of organic position i + 1; positions past the list are unaffected.
    multipliers: list[float]
    confidence: Confidence
    source: str
    url: str


FEATURES: dict[str, Feature] = {
    "ai_overview": {
        "label": "AI Overview",
        # AWR desktop CTR with an AI Overview divided by the overall desktop CTR, per position (July 2026).
        "multipliers": [0.484, 0.356, 0.437, 0.743, 0.944, 0.753, 0.761, 0.723, 0.870, 0.741],
        "confidence": "high",
        "source": "AWR, July 2026 (position 1: 9.69% vs 20.02%); Ahrefs measured a similar ~58% drop at position 1",
        "url": AWR_URL,
    },
    "local_pack": {
        "label": "Local pack (map)",
        "multipliers": [0.06],
        "confidence": "medium",
        "source": "AWR, July 2026: position 1 CTR -94% when a local pack is present (desktop)",
        "url": AWR_URL,
    },
    "images": {
        "label": "Image pack",
        "multipliers": [0.74],
        "confidence": "medium",
        "source": "AWR, July 2026: position 1 CTR -26% when images are present (desktop)",
        "url": AWR_URL,
    },
    "paid": {
        "label": "Top ads",
        "multipliers": [0.70],
        "confidence": "low",
        "source": "AWR/Caphyon 2014: position 1 CTR 25.7% without ads vs 17.9% with ads (-30%); no recent primary study found",
        "url": AWR_2014_URL,
    },
}

# Accept other providers' names for the same feature.
FEATURE_ALIASES: dict[str, str] = {
    "google_ads": "paid",
    "local_results": "local_pack",
}

# Features with no penalty, and why. Listed so the report can say they were considered.
NEUTRAL_FEATURES: dict[str, str] = {
    "people_also_ask": "AWR finds position 1 CTR is not lower (+43%) when People Also Ask is present",
    "video": "AWR finds position 1 CTR is not lower when videos are present",
    "knowledge_graph": "AWR finds about the same position 1 CTR (+5%) with a knowledge panel",
    "featured_snippet": "No reliable current data; neutral until measured",
    "answer_box": "No reliable current data; neutral until measured",
    "shopping": "No reliable current data; neutral until measured",
    "top_stories": "No reliable current data; neutral until measured",
}
