from __future__ import annotations

import hashlib
from typing import Any

from providers.base import snapshot


class MockProvider:
    """Deterministic fake SERP + volume; costs nothing."""

    name = "mock"

    def is_configured(self) -> bool:
        return True

    def fetch_serp(self, keyword: str, location_name: str, language_name: str) -> dict[str, Any]:
        seed = int(hashlib.md5(f"{keyword}{location_name}{language_name}".encode("utf-8")).hexdigest(), 16)
        total_items = 8 + (seed % 4)
        organic_count = min(6 + (seed % 3), total_items)

        items = [
            {
                "type": "organic" if i < organic_count else "featured_snippet",
                "rank_group": i + 1,
                "domain": f"example-{i + 1}.com",
            }
            for i in range(total_items)
        ]
        data = snapshot(keyword, self.name, items)
        data["keyword_data"] = {"search_volume": float(600 + (seed % 2400)), "source": "mock"}
        return data
