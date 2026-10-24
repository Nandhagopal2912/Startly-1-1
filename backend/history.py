"""Reopen saved analyses exactly as they were shown, without any API calls."""

from __future__ import annotations

import json
from typing import Any

import store
from scoring import analyze_payload


def _rescore_legacy(row: dict[str, Any]) -> dict[str, Any] | None:
    """Analyses saved before full results were stored: rebuild from their snapshot and recorded volume."""
    payload = store.snapshot_by_id(row["snapshot_id"]) if row.get("snapshot_id") else None
    if payload is None:
        return None
    has_volume = row["volume_source"] != "unknown"
    analysis = analyze_payload(
        payload,
        row["keyword"],
        volume_override=row["raw_volume"] if has_volume else None,
        volume_source=row["volume_source"] if has_volume else "user",
    )
    return {
        "source": "history",
        "mock_mode": row["provider"] == "mock",
        "provider": row["provider"],
        "rescored": True,  # numbers come from today's click model, not the one used at the time
        **analysis,
    }


def get_full_analysis(analysis_id: int) -> dict[str, Any] | None:
    row = store.analysis_row(analysis_id)
    if row is None:
        return None
    result = json.loads(row["result"]) if row.get("result") else _rescore_legacy(row)
    if result is None:
        return None
    return {**result, "analysis_id": row["id"], "analyzed_at": row["created_at"]}


def latest_full_analyses(limit: int = 20, after_id: int = 0) -> list[dict[str, Any]]:
    """The newest analysis of each recent keyword, ready to drop back into the dashboard."""
    results = (get_full_analysis(i) for i in store.latest_analysis_ids(limit, after_id))
    return [r for r in results if r is not None]
