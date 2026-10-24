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


def reset() -> None:
    with _lock:
        _hits.clear()


def client_ip(request: Request) -> str:
    if config.trust_proxy_headers():
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        limit = config.rate_limit_per_minute()
        # CORS preflights carry no work; never count or block them.
        if limit <= 0 or request.method == "OPTIONS":
            return await call_next(request)
        ip, now = client_ip(request), time.monotonic()
        with _lock:
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
