"""Turn a scored SERP into a verdict, recommended actions and the page-one ranking list."""

from __future__ import annotations

from typing import Any

# Monthly clicks across positions 1-3: at or above WORTH is "worth targeting", below LOW is "low potential".
TOP3_CLICKS_WORTH = 500
TOP3_CLICKS_LOW = 100
CLICK_HOSTILE_LOSS = 50


def page_one(items: list[dict[str, Any]], positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Organic results in ranking order with the clicks the model gives each position."""
    organic = [i for i in items if isinstance(i, dict) and i.get("type") == "organic"]
    if all(isinstance(i.get("rank_group"), int) for i in organic):
        organic = sorted(organic, key=lambda i: i["rank_group"])
    by_position = {p["position"]: p for p in positions}
    rows = []
    for pos, item in enumerate(organic[:10], start=1):
        p = by_position.get(pos, {})
        rows.append({
            "position": pos,
            "domain": item.get("domain"),
            "ctr": p.get("ctr"),
            "clicks": p.get("clicks"),
            "clicks_low": p.get("clicks_low"),
            "clicks_high": p.get("clicks_high"),
        })
    return rows


def verdict(model: dict[str, Any], has_volume: bool, loss_pct: int) -> dict[str, Any]:
    positions = model["positions"]
    if not positions:
        return {"label": "No organic slots", "tone": "bad", "top1_clicks": None, "top3_clicks": None,
                "reason": "Page one has no classic organic results to rank in."}
    if not has_volume:
        return {"label": "Add volume to decide", "tone": "unknown", "top1_clicks": None, "top3_clicks": None,
                "reason": f"Page one sends organic clicks on {model['organic_ctr_total']:.1f}% of searches. "
                          "Enter a monthly search volume to see click counts."}
    top1 = positions[0]["clicks"]
    top3 = sum(p["clicks"] for p in positions[:3])
    lost = f"SERP features take about {loss_pct}% of the clicks." if loss_pct else "Nothing on the page takes clicks."
    if top3 >= TOP3_CLICKS_WORTH:
        label, tone = "Worth targeting", "good"
    elif top3 >= TOP3_CLICKS_LOW:
        label, tone = "Modest opportunity", "neutral"
    else:
        label, tone = "Low traffic potential", "bad"
    return {"label": label, "tone": tone, "top1_clicks": top1, "top3_clicks": top3,
            "reason": f"A top-3 ranking is worth about {top3:,} clicks a month (#1 about {top1:,}). {lost}"}


def recommendations(
    *, model: dict[str, Any], types: set[str], has_volume: bool, loss_pct: int, verdict_tone: str
) -> list[dict[str, str]]:
    """Concrete next steps, most important first. tone: action | warning | info."""
    recs: list[dict[str, str]] = []
    factors = {f["feature"]: f for f in model["factors"]}

    if not has_volume:
        recs.append({"id": "add_volume", "tone": "action", "title": "Add a monthly search volume",
                     "detail": "Google Keyword Planner is free. Type the midpoint of its range into the volume box; it's saved for this keyword."})
    if not model["positions"]:
        recs.append({"id": "no_organic", "tone": "warning", "title": "Look for a related keyword",
                     "detail": "There are no organic results to rank for on this page."})
        return recs

    if "local_pack" in factors:
        recs.append({"id": "local_pack", "tone": "action", "title": "Compete in the map pack",
                     "detail": f"A local pack cuts #1 organic clicks by about {-factors['local_pack']['position_1_effect_percent']}%. "
                               "A complete Google Business Profile with reviews is the way into it."})
    if "ai_overview" in factors:
        recs.append({"id": "ai_overview", "tone": "action", "title": "Write an answer Google can cite",
                     "detail": f"An AI Overview cuts #1 clicks by about {-factors['ai_overview']['position_1_effect_percent']}%. "
                               "Put a short, direct answer near the top of the page, then go deeper than the summary can."})
    if loss_pct >= CLICK_HOSTILE_LOSS:
        recs.append({"id": "long_tail", "tone": "warning", "title": "Consider more specific keywords",
                     "detail": f"Google's own features take about {loss_pct}% of the organic clicks here. "
                               "Longer, more specific variations often have cleaner results pages."})
    if types & {"paid", "google_ads", "shopping"}:
        recs.append({"id": "commercial", "tone": "info", "title": "Searchers are ready to buy",
                     "detail": "Advertisers pay for this keyword. A ranking page should help people choose and convert: pricing, comparisons, a clear next step."})
    if "people_also_ask" in types:
        recs.append({"id": "paa", "tone": "info", "title": "Answer the People Also Ask questions",
                     "detail": "Cover those questions in your page; they show what searchers want to know next."})
    if "video" in types:
        recs.append({"id": "video", "tone": "info", "title": "A video can win extra visibility",
                     "detail": "Google shows videos for this search, so a short video can appear alongside the organic results."})
    if "images" in factors:
        recs.append({"id": "images", "tone": "info", "title": "Use original images",
                     "detail": f"An image pack takes about {-factors['images']['position_1_effect_percent']}% of #1 clicks; well-labelled original images can appear in it."})
    if has_volume and verdict_tone == "bad":
        recs.append({"id": "low_potential", "tone": "warning", "title": "Low traffic even at the top",
                     "detail": "Target this only if each visitor is very valuable, or as part of a cluster of related pages."})
    if model["low_confidence_factors"]:
        recs.append({"id": "confidence", "tone": "info", "title": "Treat the click range as approximate",
                     "detail": f"The estimate includes {', '.join(model['low_confidence_factors'])}, based on older research."})
    return recs
