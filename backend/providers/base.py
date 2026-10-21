"""Common shape every data provider returns, so scoring never depends on one API.

A SERP snapshot is a plain dict:

    {
        "keyword": "best crm",
        "provider": "serper",
        "keyword_data": {"search_volume": 1900.0, "source": "dataforseo"} | {},
        "items": [{"type": "organic", "rank_group": 1, "domain": "example.com"}, ...],
    }

Item `type` values follow DataForSEO's vocabulary (organic, paid, featured_snippet,
answer_box, knowledge_graph, people_also_ask, ai_overview, video, images, ...).
"""

from __future__ import annotations

from typing import Any, Protocol


class SerpProvider(Protocol):
    name: str

    def is_configured(self) -> bool: ...

    def fetch_serp(self, keyword: str, location_name: str, language_name: str) -> dict[str, Any]: ...


class VolumeProvider(Protocol):
    name: str

    def is_configured(self) -> bool: ...

    def fetch_volume(self, keyword: str, location_name: str, language_name: str) -> float | None: ...


def snapshot(keyword: str, provider: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"keyword": keyword, "provider": provider, "keyword_data": {}, "items": items}
