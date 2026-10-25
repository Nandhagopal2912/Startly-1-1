"""Transport and response-header protections for the API."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

import config

KEY_HEADER = "x-serpapi-key"
# Traffic to these never leaves the machine, so plain HTTP is fine for local development.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def request_scheme(request: Request) -> str:
    """https or http, as the client used it (behind a trusted proxy, from X-Forwarded-Proto)."""
    if config.trust_proxy_headers():
        forwarded = request.headers.get("x-forwarded-proto", "")
        if forwarded:
            return forwarded.split(",")[-1].strip().lower()  # the proxy's own entry is last
    return request.url.scheme


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        scheme = request_scheme(request)
        host = (request.url.hostname or "").lower()
        if request.headers.get(KEY_HEADER) and scheme != "https" and host not in LOCAL_HOSTS:
            # A key sent over plain HTTP can be read by anyone on the network. Refuse it rather than use it.
            return JSONResponse(
                status_code=400,
                content={"detail": "For your safety, API keys are only accepted over HTTPS. Use the https:// address."},
            )
        response = await call_next(request)
        # Results can describe what someone searched for: don't let browsers or proxies keep copies.
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
