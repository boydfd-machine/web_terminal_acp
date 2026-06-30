from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.datastructures import URL
from starlette.requests import Request as StarletteRequest

from app.auth import AuthMiddleware
from app.config import get_settings
from app.platform.csrf import CsrfProtectionMiddleware
from app.platform.security_rate_limit import SecurityRateLimitMiddleware
from app.platform.security_store import reset_security_store_for_tests


def _make_api_app(*middleware_classes) -> FastAPI:
    app = FastAPI()
    for middleware_class in middleware_classes:
        app.add_middleware(middleware_class)

    @app.api_route("/api/protected", methods=["GET", "POST"])
    async def protected():
        return {"ok": True}

    @app.post("/api/clients/register")
    async def register_client():
        return {"ok": True}

    return app


def _misreport_request_url_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        StarletteRequest,
        "url",
        property(lambda self: URL("http://testserver/healthz")),
    )


@pytest.mark.asyncio
async def test_auth_middleware_uses_scope_path_for_security_decision(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "web_terminal_auth_secret", "login-secret")
    monkeypatch.setattr(settings, "web_terminal_disable_auth_for_tests", False)
    _misreport_request_url_path(monkeypatch)

    app = _make_api_app(AuthMiddleware)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/protected")

    assert response.status_code == 401
    assert response.json()["detail"] == "login required"


@pytest.mark.asyncio
async def test_csrf_middleware_uses_scope_path_for_security_decision(monkeypatch):
    _misreport_request_url_path(monkeypatch)

    app = _make_api_app(CsrfProtectionMiddleware)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/protected",
            headers={"Origin": "https://evil.example"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "cross-site request rejected"


@pytest.mark.asyncio
async def test_rate_limit_middleware_uses_scope_path_for_security_decision(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "web_terminal_disable_security_rate_limits_for_tests", False)
    _misreport_request_url_path(monkeypatch)
    await reset_security_store_for_tests()

    app = _make_api_app(SecurityRateLimitMiddleware)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            responses = [
                await client.post(
                    "/api/clients/register",
                    headers={"X-Forwarded-For": "198.51.100.21"},
                )
                for _ in range(4)
            ]
    finally:
        await reset_security_store_for_tests()

    assert [response.status_code for response in responses] == [200, 200, 200, 429]
    assert responses[-1].json()["detail"] == "rate limit exceeded"
