"""Per-IP sliding-window rate limit, kept in memory (fine for one server process)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

import config

WINDOW_SECONDS = 60

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()
_last_prune = time.monotonic()


def reset() -> None:
    global _last_prune
    with _lock:
        _hits.clear()
        _last_prune = time.monotonic()


def client_ip(request: Request) -> str:
    """The visitor's IP. Behind trusted proxies, read X-Forwarded-For from the right: each proxy appends the
    address it saw, while everything to the left of our own proxies' entries came from the client and can be faked."""
    if config.trust_proxy_headers():
        entries = [e.strip() for e in request.headers.get("x-forwarded-for", "").split(",") if e.strip()]
        if entries:
            return entries[max(len(entries) - config.trusted_proxy_hops(), 0)]
    return request.client.host if request.client else "unknown"


def _prune(now: float) -> None:
    """Forget IPs with no requests in the last window, so one-time visitors don't stay in memory. Call with _lock held."""
    global _last_prune
    if now - _last_prune < WINDOW_SECONDS:
        return
    for ip in [ip for ip, hits in _hits.items() if not hits or now - hits[-1] >= WINDOW_SECONDS]:
        del _hits[ip]
    _last_prune = now


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        limit = config.rate_limit_per_minute()
        # CORS preflights carry no work; never count or block them.
        if limit <= 0 or request.method == "OPTIONS":
            return await call_next(request)
        ip, now = client_ip(request), time.monotonic()
        with _lock:
            _prune(now)
            hits = _hits[ip]
            while hits and now - hits[0] >= WINDOW_SECONDS:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, int(WINDOW_SECONDS - (now - hits[0])) + 1)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please wait a minute and try again."},
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)
        return await call_next(request)
