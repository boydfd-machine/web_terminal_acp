import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app


@pytest.mark.asyncio
async def test_cross_site_origin_is_rejected_for_unsafe_api_requests():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            headers={"Origin": "https://evil.example"},
            json={"secret": "login-secret"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "cross-site request rejected"


@pytest.mark.asyncio
async def test_cross_site_fetch_metadata_is_rejected_without_origin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            headers={"Sec-Fetch-Site": "cross-site"},
            json={"secret": "login-secret"},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_browser_unsafe_api_request_without_origin_is_allowed():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/login", json={"secret": "login-secret"})

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_configured_frontend_origin_is_allowed(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "cors_allow_origins", "https://ui.example")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            headers={"Origin": "https://ui.example"},
            json={"secret": "login-secret"},
        )

    assert response.status_code == 200
