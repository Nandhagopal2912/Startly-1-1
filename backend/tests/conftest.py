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
    """Use a temp SQLite database and clear real API settings, so tests never touch real data or spend credits."""
    import db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    for name in ("SERPER_API_KEY", "SERPAPI_API_KEY", "DATAFORSEO_EMAIL", "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SERP_PROVIDER", "serper")
    monkeypatch.setenv("VOLUME_PROVIDER", "none")
    monkeypatch.setenv("MAX_API_CALLS_PER_DAY", "50")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")  # tests that check rate limiting turn it back on
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    import credits
    import ratelimit

    ratelimit.reset()
    credits.clear_cache()
    yield tmp_path
