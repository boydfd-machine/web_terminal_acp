from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from app.auth import AuthIdentity, verify_browser_token
from app.config import get_settings
from app.platform.keycloak import (
    exchange_keycloak_authorization_code,
    keycloak_config,
    keycloak_public_config,
    refresh_keycloak_token,
)


@pytest.fixture
def key_pair():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _keycloak_token(private_key, *, issuer: str, audience: str = "web-terminal") -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": "user-123",
            "preferred_username": "alice",
            "email": "alice@example.com",
            "name": "Alice Doe",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


def _keycloak_access_token_with_azp(private_key, *, issuer: str, client_id: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": issuer,
            "aud": "account",
            "azp": client_id,
            "sub": "user-123",
            "preferred_username": "alice",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


def test_keycloak_public_config_uses_realm_metadata(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web_terminal")

    config = keycloak_public_config(keycloak_config(settings))

    assert config == {
        "base_url": "https://auth.example.com",
        "realm": "home",
        "client_id": "web_terminal",
        "issuer": "https://auth.example.com/realms/home",
        "authorization_endpoint": "https://auth.example.com/realms/home/protocol/openid-connect/auth",
        "token_endpoint": "https://auth.example.com/realms/home/protocol/openid-connect/token",
        "end_session_endpoint": "https://auth.example.com/realms/home/protocol/openid-connect/logout",
    }


@pytest.mark.asyncio
async def test_exchange_keycloak_authorization_code_returns_access_and_refresh_tokens(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web_terminal")
    monkeypatch.setattr(settings, "keycloak_client_secret", "client-secret")
    captured = _mock_keycloak_token_response(
        monkeypatch,
        {"access_token": "access-1", "refresh_token": "refresh-1"},
    )
    config = keycloak_config(settings)
    assert config is not None

    token_set = await exchange_keycloak_authorization_code(
        config,
        code="auth-code",
        redirect_uri="http://localhost/callback",
        code_verifier="verifier",
    )

    assert token_set.access_token == "access-1"
    assert token_set.refresh_token == "refresh-1"
    assert captured == {
        "timeout": 10.0,
        "url": "https://auth.example.com/realms/home/protocol/openid-connect/token",
        "data": {
            "grant_type": "authorization_code",
            "client_id": "web_terminal",
            "client_secret": "client-secret",
            "code": "auth-code",
            "redirect_uri": "http://localhost/callback",
            "code_verifier": "verifier",
        },
    }


@pytest.mark.asyncio
async def test_refresh_keycloak_token_uses_refresh_grant_and_keeps_existing_refresh_token(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web_terminal")
    monkeypatch.setattr(settings, "keycloak_client_secret", None)
    captured = _mock_keycloak_token_response(monkeypatch, {"access_token": "access-2"})
    config = keycloak_config(settings)
    assert config is not None

    token_set = await refresh_keycloak_token(config, refresh_token="refresh-1")

    assert token_set.access_token == "access-2"
    assert token_set.refresh_token == "refresh-1"
    assert captured == {
        "timeout": 10.0,
        "url": "https://auth.example.com/realms/home/protocol/openid-connect/token",
        "data": {
            "grant_type": "refresh_token",
            "client_id": "web_terminal",
            "refresh_token": "refresh-1",
        },
    }


def test_verify_browser_token_accepts_keycloak_access_token(monkeypatch, key_pair):
    settings = get_settings()
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")
    monkeypatch.setattr(settings, "keycloak_public_key_pem", _public_key_pem(key_pair))

    token = _keycloak_token(key_pair, issuer="https://auth.example.com/realms/home")

    identity = verify_browser_token(token)

    assert identity == AuthIdentity(
        user_id="user-123",
        username="alice",
        email="alice@example.com",
        display_name="Alice Doe",
        auth_provider="keycloak",
    )


def test_verify_browser_token_accepts_keycloak_azp_client_claim(monkeypatch, key_pair):
    settings = get_settings()
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")
    monkeypatch.setattr(settings, "keycloak_public_key_pem", _public_key_pem(key_pair))

    token = _keycloak_access_token_with_azp(
        key_pair,
        issuer="https://auth.example.com/realms/home",
        client_id="web-terminal",
    )

    identity = verify_browser_token(token)

    assert identity is not None
    assert identity.user_id == "user-123"


def test_verify_browser_token_rejects_wrong_keycloak_issuer(monkeypatch, key_pair):
    settings = get_settings()
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")
    monkeypatch.setattr(settings, "keycloak_public_key_pem", _public_key_pem(key_pair))

    token = _keycloak_token(key_pair, issuer="https://evil.example.com/realms/home")

    assert verify_browser_token(token) is None


def _public_key_pem(private_key) -> str:
    public_key = private_key.public_key()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def _mock_keycloak_token_response(monkeypatch, body: dict[str, str]) -> dict[str, object]:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return body

    class FakeAsyncClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def post(self, url: str, data: dict[str, str]) -> FakeResponse:
            captured["url"] = url
            captured["data"] = dict(data)
            return FakeResponse()

    monkeypatch.setattr("app.platform.keycloak.httpx.AsyncClient", FakeAsyncClient)
    return captured
