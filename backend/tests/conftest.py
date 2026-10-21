from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(BACKEND_DIR))


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Point cache + usage files at a temp dir and clear real API settings, so tests never spend credits."""
    import cache
    import usage

    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(usage, "_USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(usage, "_LOG_FILE", tmp_path / "api_calls.log")
    for name in ("SERPER_API_KEY", "DATAFORSEO_EMAIL", "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SERP_PROVIDER", "serper")
    monkeypatch.setenv("VOLUME_PROVIDER", "none")
    monkeypatch.setenv("MAX_API_CALLS_PER_DAY", "50")
    yield tmp_path
