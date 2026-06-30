from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.platform.security_rate_limit import (
    GENERAL_WRITE_RULES,
    SecurityRateLimitMiddleware,
    client_ip_from_headers,
    consume_rate_limit,
)
from app.platform.security_store import SecurityStore, reset_security_store_for_tests


@pytest.mark.asyncio
async def test_client_registration_rate_limit_blocks_fourth_attempt():
    await reset_security_store_for_tests()
    rule = GENERAL_WRITE_RULES["client-registration"]

    results = [await consume_rate_limit(rule, "203.0.113.10") for _ in range(4)]

    assert [result.allowed for result in results] == [True, True, True, False]
    assert results[-1].limit == 3
    assert results[-1].retry_after_seconds > 0


@pytest.mark.asyncio
async def test_window_create_rate_limit_allows_sixty_then_blocks_next():
    await reset_security_store_for_tests()
    rule = GENERAL_WRITE_RULES["window-create"]

    results = [await consume_rate_limit(rule, "203.0.113.11") for _ in range(61)]

    assert all(result.allowed for result in results[:60])
    assert not results[60].allowed
    assert results[60].limit == 60


@pytest.mark.asyncio
async def test_rate_limit_middleware_blocks_client_registration_when_enabled():
    settings = get_settings()
    previous = settings.web_terminal_disable_security_rate_limits_for_tests
    settings.web_terminal_disable_security_rate_limits_for_tests = False
    await reset_security_store_for_tests()
    app = FastAPI()
    app.add_middleware(SecurityRateLimitMiddleware)

    @app.post("/api/clients/register")
    async def register_client():
        return {"ok": True}

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            responses = [
                await client.post(
                    "/api/clients/register",
                    headers={"X-Forwarded-For": "198.51.100.20"},
                )
                for _ in range(4)
            ]
    finally:
        settings.web_terminal_disable_security_rate_limits_for_tests = previous
        await reset_security_store_for_tests()

    assert [response.status_code for response in responses] == [200, 200, 200, 429]
    assert responses[-1].json()["detail"] == "rate limit exceeded"
    assert responses[-1].headers["retry-after"].isdigit()


def test_client_ip_prefers_forwarded_for_first_hop():
    from starlette.datastructures import Headers

    headers = Headers({"X-Forwarded-For": "203.0.113.7, 10.0.0.1"})

    assert client_ip_from_headers(headers, "127.0.0.1") == "203.0.113.7"


@pytest.mark.asyncio
async def test_security_store_does_not_fallback_when_redis_returns_none(monkeypatch):
    store = SecurityStore()

    async def run_redis_operation(operation):
        return None

    monkeypatch.setattr(store, "_run_redis", run_redis_operation)
    await store.set_captcha("captcha-1", {"answer_hash": "hash"}, ttl_seconds=60)

    assert await store.pop_captcha("captcha-1") is None
