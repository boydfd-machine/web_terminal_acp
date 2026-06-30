from __future__ import annotations

import re
from urllib.parse import urlsplit

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import get_settings
from app.platform.request_path import request_scope_path

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_LOCALHOST_ORIGIN_RE = re.compile(r"^https?://(?:127\.0\.0\.1|localhost)(?::\d+)?$")


class CsrfProtectionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if _should_reject_cross_site_request(request):
            return JSONResponse(
                {"detail": "cross-site request rejected"},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return await call_next(request)


def _should_reject_cross_site_request(request: Request) -> bool:
    if request.method.upper() not in _UNSAFE_METHODS:
        return False
    if not request_scope_path(request).startswith("/api/"):
        return False

    origin = request.headers.get("origin")
    if origin is not None:
        return not _is_trusted_origin(origin, request)

    fetch_site = request.headers.get("sec-fetch-site")
    return fetch_site == "cross-site"


def _is_trusted_origin(origin: str, request: Request) -> bool:
    normalized = origin.strip().rstrip("/")
    if not normalized:
        return False
    if normalized == _request_origin(request):
        return True
    if _LOCALHOST_ORIGIN_RE.fullmatch(normalized):
        return True
    return normalized in _configured_cors_origins()


def _request_origin(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


def _configured_cors_origins() -> set[str]:
    configured = get_settings().cors_allow_origins
    if configured is None or not configured.strip():
        return set()
    return {
        parsed
        for origin in configured.split(",")
        if (parsed := _normalized_origin(origin)) is not None
    }


def _normalized_origin(origin: str) -> str | None:
    value = origin.strip().rstrip("/")
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"
