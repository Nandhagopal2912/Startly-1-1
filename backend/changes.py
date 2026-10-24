"""What changed on a results page between two checks of the same keyword (no API calls)."""

from __future__ import annotations

from collections import Counter
from typing import Any

import store
from ctr_config import FEATURES
from scoring import analyze_payload, first_result

# How many moved / new / dropped domains to describe in the summary sentences.
SUMMARY_DOMAIN_LIMIT = 3


def feature_label(item_type: str) -> str:
    if item_type in FEATURES:
        return FEATURES[item_type]["label"]
    return item_type.replace("_", " ").capitalize()


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = first_result(payload).get("items") or []
    return [i for i in items if isinstance(i, dict)]


def _feature_counts(items: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(i["type"]) for i in items if i.get("type") and i.get("type") != "organic")


def _organic_positions(items: list[dict[str, Any]]) -> dict[str, int]:
    """Domain -> 1-based organic position (first appearance wins)."""
    organic = [i for i in items if i.get("type") == "organic"]
    if all(isinstance(i.get("rank_group"), int) for i in organic):
        organic.sort(key=lambda i: i["rank_group"])
    positions: dict[str, int] = {}
    for pos, item in enumerate(organic, start=1):
        domain = item.get("domain")
        if domain and domain not in positions:
            positions[str(domain)] = pos
    return positions


def diff_snapshots(
    before: dict[str, Any],
    after: dict[str, Any],
    keyword: str,
    volume: float | None = None,
    volume_source: str = "user",
) -> dict[str, Any]:
    """Compare two snapshots; both are scored with the same volume so click changes come from the page alone."""
    old_items, new_items = _items(before), _items(after)
    old_counts, new_counts = _feature_counts(old_items), _feature_counts(new_items)
    added = sorted(t for t in new_counts if t not in old_counts)
    removed = sorted(t for t in old_counts if t not in new_counts)
    count_changes = [
        {"type": t, "label": feature_label(t), "before": old_counts[t], "after": new_counts[t]}
        for t in sorted(set(old_counts) & set(new_counts))
        if old_counts[t] != new_counts[t]
    ]

    old_pos, new_pos = _organic_positions(old_items), _organic_positions(new_items)
    entered = sorted(({"domain": d, "position": p} for d, p in new_pos.items() if d not in old_pos), key=lambda x: x["position"])
    left = sorted(({"domain": d, "position": p} for d, p in old_pos.items() if d not in new_pos), key=lambda x: x["position"])
    moved = sorted(
        ({"domain": d, "before": old_pos[d], "after": p} for d, p in new_pos.items() if d in old_pos and old_pos[d] != p),
        key=lambda x: (-abs(x["before"] - x["after"]), x["after"]),
    )

    old_a = analyze_payload(before, keyword, volume_override=volume, volume_source=volume_source)
    new_a = analyze_payload(after, keyword, volume_override=volume, volume_source=volume_source)
    clicks_before, clicks_after = old_a["capturable_clicks"], new_a["capturable_clicks"]
    ctr_before = old_a["report"]["summary"]["organic_ctr_total"]
    ctr_after = new_a["report"]["summary"]["organic_ctr_total"]
    organic_before = sum(1 for i in old_items if i.get("type") == "organic")
    organic_after = sum(1 for i in new_items if i.get("type") == "organic")

    sentences: list[str] = []
    sentences += [f"{feature_label(t)} appeared." for t in added]
    sentences += [f"{feature_label(t)} disappeared." for t in removed]
    sentences += [f"{c['label']}: {c['before']} → {c['after']}." for c in count_changes]
    if organic_before != organic_after:
        sentences.append(f"Organic results on page one: {organic_before} → {organic_after}.")
    if clicks_before is not None and clicks_after is not None and clicks_before != clicks_after:
        change = f" ({(clicks_after - clicks_before) / clicks_before * 100:+.0f}%)" if clicks_before else ""
        sentences.append(f"Capturable clicks: {clicks_before:,} → {clicks_after:,}{change}.")
    elif clicks_before is None and abs(ctr_after - ctr_before) >= 0.05:
        sentences.append(f"Organic click-through: {ctr_before:.1f}% → {ctr_after:.1f}% of searches.")
    sentences += [f"{m['domain']} moved #{m['before']} → #{m['after']}." for m in moved[:SUMMARY_DOMAIN_LIMIT]]
    sentences += [f"New on page one: {e['domain']} (#{e['position']})." for e in entered[:SUMMARY_DOMAIN_LIMIT]]
    sentences += [f"Dropped off page one: {d['domain']} (was #{d['position']})." for d in left[:SUMMARY_DOMAIN_LIMIT]]

    has_changes = bool(added or removed or count_changes or entered or left or moved or organic_before != organic_after)
    return {
        "has_previous": True,
        "has_changes": has_changes,
        "summary": sentences if has_changes else ["No changes since the previous check."],
        "features_added": [{"type": t, "label": feature_label(t)} for t in added],
        "features_removed": [{"type": t, "label": feature_label(t)} for t in removed],
        "feature_counts_changed": count_changes,
        "organic_before": organic_before,
        "organic_after": organic_after,
        "domains_entered": entered,
        "domains_left": left,
        "domains_moved": moved,
        "clicks_before": clicks_before,
        "clicks_after": clicks_after,
        "ctr_before": ctr_before,
        "ctr_after": ctr_after,
        "click_loss_before": old_a["report"]["summary"]["penalty_percent"],
        "click_loss_after": new_a["report"]["summary"]["penalty_percent"],
    }


def changes_since_previous(
    snapshot_id: int, payload: dict[str, Any], keyword: str, volume: float | None, volume_source: str
) -> dict[str, Any]:
    """Diff this snapshot against the previous one for the same keyword, location, language and mode."""
    info = store.snapshot_and_previous(snapshot_id)
    if info is None:
        return {"has_previous": False, "current_fetched_at": None}
    current_at, previous = info
    if previous is None:
        return {"has_previous": False, "current_fetched_at": current_at}
    _, previous_payload, previous_at = previous
    diff = diff_snapshots(previous_payload, payload, keyword, volume, volume_source or "user")
    return {**diff, "previous_fetched_at": previous_at, "current_fetched_at": current_at}
