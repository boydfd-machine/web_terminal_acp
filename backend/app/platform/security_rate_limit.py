from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers
from starlette.types import ASGIApp

from app.config import get_settings
from app.platform.request_path import request_scope_path
from app.platform.security_store import get_security_store

LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60


@dataclass(frozen=True)
class RateLimitRule:
    scope: str
    limit: int
    window_seconds: int


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    count: int
    limit: int
    retry_after_seconds: int


GENERAL_WRITE_RULES = {
    "auth-captcha": RateLimitRule(
        scope="auth-captcha",
        limit=20,
        window_seconds=60,
    ),
    "client-registration": RateLimitRule(
        scope="client-registration",
        limit=3,
        window_seconds=60 * 60,
    ),
    "window-create": RateLimitRule(
        scope="window-create",
        limit=60,
        window_seconds=60,
    ),
}


def client_ip_from_request(request: Request) -> str:
    return client_ip_from_headers(request.headers, request.client.host if request.client else None)


def client_ip_from_headers(headers: Headers, fallback: str | None) -> str:
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        for candidate in forwarded_for.split(","):
            normalized = _normalize_ip(candidate.strip())
            if normalized:
                return normalized
    real_ip = _normalize_ip(headers.get("x-real-ip"))
    if real_ip:
        return real_ip
    return _normalize_ip(fallback) or "unknown"


async def increment_failed_login(ip_address_text: str) -> RateLimitResult:
    state = await get_security_store().increment_counter(
        "auth-login-failed",
        ip_address_text,
        LOGIN_FAILURE_WINDOW_SECONDS,
    )
    await get_security_store().record_event(
        {
            "type": "login_failed",
            "scope": "auth-login-failed",
            "identity": ip_address_text,
            "count": state.count,
            "limit": LOGIN_FAILURE_LIMIT,
        }
    )
    if state.count >= LOGIN_FAILURE_LIMIT:
        await get_security_store().record_event(
            {
                "type": "rate_limited",
                "scope": "auth-login-failed",
                "identity": ip_address_text,
                "count": state.count,
                "limit": LOGIN_FAILURE_LIMIT,
            }
        )
    return RateLimitResult(
        allowed=state.count < LOGIN_FAILURE_LIMIT,
        count=state.count,
        limit=LOGIN_FAILURE_LIMIT,
        retry_after_seconds=state.retry_after_seconds,
    )


async def login_requires_captcha(ip_address_text: str) -> tuple[bool, int]:
    state = await get_security_store().read_counter("auth-login-failed", ip_address_text)
    return state.count >= LOGIN_FAILURE_LIMIT, state.retry_after_seconds


async def clear_failed_login(ip_address_text: str) -> None:
    await get_security_store().clear_counter("auth-login-failed", ip_address_text)


async def consume_rate_limit(rule: RateLimitRule, identity: str) -> RateLimitResult:
    state = await get_security_store().increment_counter(rule.scope, identity, rule.window_seconds)
    allowed = state.count <= rule.limit
    if not allowed:
        await get_security_store().record_event(
            {
                "type": "rate_limited",
                "scope": rule.scope,
                "identity": identity,
                "count": state.count,
                "limit": rule.limit,
            }
        )
    return RateLimitResult(
        allowed=allowed,
        count=state.count,
        limit=rule.limit,
        retry_after_seconds=state.retry_after_seconds,
    )


def rule_for_request(request: Request) -> RateLimitRule | None:
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    path = request_scope_path(request)
    if path == "/api/auth/login":
        return None
    if path == "/api/auth/captcha":
        return GENERAL_WRITE_RULES["auth-captcha"]
    if path == "/api/clients/register":
        return GENERAL_WRITE_RULES["client-registration"]
    if _is_window_create_path(path):
        return GENERAL_WRITE_RULES["window-create"]
    return None


class SecurityRateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if get_settings().web_terminal_disable_security_rate_limits_for_tests:
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)
        rule = rule_for_request(request)
        if rule is None:
            await self.app(scope, receive, send)
            return
        result = await consume_rate_limit(rule, client_ip_from_request(request))
        if result.allowed:
            await self.app(scope, receive, send)
            return
        response = rate_limit_response(result, "rate limit exceeded")
        await response(scope, receive, send)


def rate_limit_response(result: RateLimitResult, detail: str, *, code: str | None = None) -> JSONResponse:
    body: dict[str, object] = {
        "detail": detail,
        "retry_after_seconds": result.retry_after_seconds,
        "limit": result.limit,
    }
    if code is not None:
        body["code"] = code
    return JSONResponse(
        body,
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={"Retry-After": str(result.retry_after_seconds)},
    )


def _is_window_create_path(path: str) -> bool:
    if path == "/api/windows":
        return True
    parts = path.strip("/").split("/")
    if len(parts) == 4 and parts[0] == "api" and parts[1] == "clients" and parts[3] == "windows":
        return True
    return (
        len(parts) == 6
        and parts[0] == "api"
        and parts[1] == "clients"
        and parts[3] == "windows"
        and parts[5] == "clone"
    )


def _normalize_ip(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    try:
        return str(ip_address(value.strip()))
    except ValueError:
        return value.strip()[:128]
