from __future__ import annotations

from fastapi import HTTPException

from config import serp_provider_name, volume_provider_name
from providers.base import SerpProvider, VolumeProvider
from providers.dataforseo import DataForSeoProvider
from providers.mock import MockProvider
from providers.serper import SerperProvider

_SERP_PROVIDERS: dict[str, type] = {
    "serper": SerperProvider,
    "dataforseo": DataForSeoProvider,
    "mock": MockProvider,
}
_VOLUME_PROVIDERS: dict[str, type] = {
    "dataforseo": DataForSeoProvider,
}


def get_serp_provider(name: str | None = None) -> SerpProvider:
    key = (name or serp_provider_name()).lower()
    cls = _SERP_PROVIDERS.get(key)
    if cls is None:
        raise HTTPException(
            status_code=500,
            detail=f"Unknown SERP_PROVIDER '{key}'. Use one of: {', '.join(_SERP_PROVIDERS)}.",
        )
    return cls()


def get_volume_provider() -> VolumeProvider | None:
    """The configured volume source, or None when VOLUME_PROVIDER=none."""
    cls = _VOLUME_PROVIDERS.get(volume_provider_name())
    return cls() if cls else None
