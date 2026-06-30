from cryptography.hazmat.primitives.asymmetric import rsa
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.websockets import WebSocketDisconnect
from app.auth import create_agent_ops_token, create_mcp_token, create_session_token
from app.config import get_settings
from app.contexts.clients.infrastructure.repository import create_client
from app.main import app
from app.models import Client, ClientRuntime
from app.platform import auth_routes, captcha_service
from app.platform.security_store import reset_security_store_for_tests

pytest_plugins = ("tests.integration.auth_api_support",)


def _public_key_pem(private_key) -> str:
    from tests.integration.auth_api_support import public_key_pem

    return public_key_pem(private_key)


def _keycloak_token(private_key, **kwargs) -> str:
    from tests.integration.auth_api_support import keycloak_token

    return keycloak_token(private_key, **kwargs)


def _websocket_auth_test_app():
    from tests.integration.auth_api_support import websocket_auth_test_app

    return websocket_auth_test_app()


@pytest.mark.asyncio
async def test_auth_required_for_api_when_secret_configured():
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    settings.web_terminal_auth_secret = "login-secret"
    settings.web_terminal_disable_auth_for_tests = False
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            rejected = await client.get("/api/clients")
            bad_login = await client.post("/api/auth/login", json={"secret": "wrong"})
            login = await client.post("/api/auth/login", json={"secret": "login-secret"})
            token = login.json()["token"]
            accepted = await client.get(
                "/api/missing-route",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable
    assert rejected.status_code == 401
    assert bad_login.status_code == 401
    assert login.status_code == 200
    assert accepted.status_code != 401

@pytest.mark.asyncio
async def test_login_accepts_empty_captcha_fields_as_absent():
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    settings.web_terminal_auth_secret = "login-secret"
    settings.web_terminal_disable_auth_for_tests = False
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/auth/login",
                json={
                    "secret": "login-secret",
                    "captcha_id": "",
                    "captcha_answer": "",
                },
            )
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable
    assert login.status_code == 200
    assert login.json()["token"]

@pytest.mark.asyncio
async def test_keycloak_auth_status_exposes_public_oidc_config(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "web_terminal_disable_auth_for_tests", False)
    monkeypatch.setattr(settings, "web_terminal_auth_secret", None)
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/auth/status")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "mode": "keycloak",
        "keycloak": {
            "base_url": "https://auth.example.com",
            "realm": "home",
            "client_id": "web-terminal",
            "issuer": "https://auth.example.com/realms/home",
            "authorization_endpoint": (
                "https://auth.example.com/realms/home/protocol/openid-connect/auth"
            ),
            "token_endpoint": "https://auth.example.com/realms/home/protocol/openid-connect/token",
            "end_session_endpoint": (
                "https://auth.example.com/realms/home/protocol/openid-connect/logout"
            ),
        },
    }


@pytest.mark.asyncio
async def test_keycloak_bearer_token_limits_clients_to_current_user(
    auth_db_client,
    monkeypatch,
):
    settings = get_settings()
    key_pair = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "web_terminal_disable_auth_for_tests", False)
    monkeypatch.setattr(settings, "web_terminal_auth_secret", None)
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")
    monkeypatch.setattr(settings, "keycloak_public_key_pem", _public_key_pem(key_pair))

    async with auth_db_client.session_factory() as session:
        alice_client, _ = await create_client(
            session,
            name="alice-client",
            runtime=ClientRuntime.remote,
            owner_user_id="alice",
        )
        bob_client, _ = await create_client(
            session,
            name="bob-client",
            runtime=ClientRuntime.remote,
            owner_user_id="bob",
        )
        await session.commit()

    alice_token = _keycloak_token(key_pair, subject="alice", username="alice")
    bob_token = _keycloak_token(key_pair, subject="bob", username="bob")

    alice_response = await auth_db_client.get(
        "/api/clients",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    bob_direct_response = await auth_db_client.get(
        f"/api/clients/{alice_client.id}",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    alice_delete_bob = await auth_db_client.delete(
        f"/api/clients/{bob_client.id}",
        headers={"Authorization": f"Bearer {alice_token}"},
    )

    assert alice_response.status_code == 200
    assert [client["id"] for client in alice_response.json()] == [str(alice_client.id)]
    assert str(bob_client.id) not in {client["id"] for client in alice_response.json()}
    assert bob_direct_response.status_code == 404
    assert alice_delete_bob.status_code == 404


@pytest.mark.asyncio
async def test_keycloak_mode_rejects_password_session_tokens(auth_db_client, monkeypatch):
    settings = get_settings()
    key_pair = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "web_terminal_disable_auth_for_tests", False)
    monkeypatch.setattr(settings, "web_terminal_auth_secret", "legacy-secret")
    monkeypatch.setattr(settings, "keycloak_base_url", None)
    monkeypatch.setattr(settings, "keycloak_realm", None)
    monkeypatch.setattr(settings, "keycloak_client_id", None)
    legacy_token = create_session_token()
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")
    monkeypatch.setattr(settings, "keycloak_public_key_pem", _public_key_pem(key_pair))

    response = await auth_db_client.get(
        "/api/clients",
        headers={"Authorization": f"Bearer {legacy_token}"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_password_session_token_keeps_client_routes_compatible(auth_db_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "web_terminal_disable_auth_for_tests", False)
    monkeypatch.setattr(settings, "web_terminal_auth_secret", "login-secret")
    monkeypatch.setattr(settings, "keycloak_base_url", None)
    monkeypatch.setattr(settings, "keycloak_realm", None)
    monkeypatch.setattr(settings, "keycloak_client_id", None)
    token = create_session_token()

    async with auth_db_client.session_factory() as session:
        remote_client, _ = await create_client(
            session,
            name="legacy-client",
            runtime=ClientRuntime.remote,
        )
        await session.commit()

    response = await auth_db_client.get(
        f"/api/clients/{remote_client.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "legacy-client"


@pytest.mark.asyncio
async def test_keycloak_listing_claims_legacy_unowned_clients(auth_db_client, monkeypatch):
    settings = get_settings()
    key_pair = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "web_terminal_disable_auth_for_tests", False)
    monkeypatch.setattr(settings, "web_terminal_auth_secret", None)
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")
    monkeypatch.setattr(settings, "keycloak_public_key_pem", _public_key_pem(key_pair))

    async with auth_db_client.session_factory() as session:
        legacy_client, _ = await create_client(
            session,
            name="legacy-client",
            runtime=ClientRuntime.remote,
        )
        await session.commit()

    alice_token = _keycloak_token(key_pair, subject="alice", username="alice")
    bob_token = _keycloak_token(key_pair, subject="bob", username="bob")

    alice_response = await auth_db_client.get(
        "/api/clients",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    bob_response = await auth_db_client.get(
        "/api/clients",
        headers={"Authorization": f"Bearer {bob_token}"},
    )

    assert alice_response.status_code == 200
    assert [client["id"] for client in alice_response.json()] == [str(legacy_client.id)]
    assert bob_response.status_code == 200
    assert bob_response.json() == []

    async with auth_db_client.session_factory() as session:
        claimed = await session.get(Client, legacy_client.id)
        assert claimed is not None
        assert claimed.owner_user_id == "alice"


@pytest.mark.asyncio
async def test_keycloak_callback_exchanges_code_on_backend(
    auth_db_client,
    monkeypatch,
):
    settings = get_settings()
    key_pair = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _keycloak_token(key_pair, subject="alice", username="alice")
    captured = {}
    monkeypatch.setattr(settings, "web_terminal_disable_auth_for_tests", False)
    monkeypatch.setattr(settings, "web_terminal_auth_secret", None)
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")
    monkeypatch.setattr(settings, "keycloak_client_secret", "client-secret")
    monkeypatch.setattr(settings, "keycloak_public_key_pem", _public_key_pem(key_pair))

    async def fake_exchange(config, *, code, redirect_uri, code_verifier):
        captured.update(
            {
                "client_secret": config.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            }
        )
        return {"access_token": token, "refresh_token": "refresh-token"}

    monkeypatch.setattr(auth_routes, "exchange_keycloak_authorization_code", fake_exchange)

    response = await auth_db_client.post(
        "/api/auth/keycloak/callback",
        json={
            "code": "auth-code",
            "redirect_uri": "http://127.0.0.1:5173/",
            "code_verifier": "verifier",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"token": token, "refresh_token": "refresh-token", "enabled": True}
    assert captured == {
        "client_secret": "client-secret",
        "code": "auth-code",
        "redirect_uri": "http://127.0.0.1:5173/",
        "code_verifier": "verifier",
    }


@pytest.mark.asyncio
async def test_keycloak_refresh_exchanges_refresh_token_without_access_token(
    auth_db_client,
    monkeypatch,
):
    settings = get_settings()
    key_pair = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _keycloak_token(key_pair, subject="alice", username="alice")
    captured = {}
    monkeypatch.setattr(settings, "web_terminal_disable_auth_for_tests", False)
    monkeypatch.setattr(settings, "web_terminal_auth_secret", None)
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")
    monkeypatch.setattr(settings, "keycloak_client_secret", "client-secret")
    monkeypatch.setattr(settings, "keycloak_public_key_pem", _public_key_pem(key_pair))

    async def fake_refresh(config, *, refresh_token):
        captured.update(
            {
                "client_secret": config.client_secret,
                "refresh_token": refresh_token,
            }
        )
        return {"access_token": token, "refresh_token": "refresh-token-2"}

    monkeypatch.setattr(auth_routes, "refresh_keycloak_token", fake_refresh, raising=False)

    response = await auth_db_client.post(
        "/api/auth/refresh",
        json={"refresh_token": "refresh-token-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"token": token, "refresh_token": "refresh-token-2", "enabled": True}
    assert captured == {
        "client_secret": "client-secret",
        "refresh_token": "refresh-token-1",
    }


@pytest.mark.asyncio
async def test_keycloak_refresh_rejects_invalid_refresh_token(
    auth_db_client,
    monkeypatch,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "web_terminal_disable_auth_for_tests", False)
    monkeypatch.setattr(settings, "web_terminal_auth_secret", None)
    monkeypatch.setattr(settings, "keycloak_base_url", "https://auth.example.com/")
    monkeypatch.setattr(settings, "keycloak_realm", "home")
    monkeypatch.setattr(settings, "keycloak_client_id", "web-terminal")

    async def fake_refresh(config, *, refresh_token):
        raise ValueError("refresh failed")

    monkeypatch.setattr(auth_routes, "refresh_keycloak_token", fake_refresh, raising=False)

    response = await auth_db_client.post(
        "/api/auth/refresh",
        json={"refresh_token": "expired-refresh-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "refresh token invalid"


@pytest.mark.asyncio
async def test_login_requires_captcha_after_repeated_failed_attempts(monkeypatch):
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    previous_limits = settings.web_terminal_disable_security_rate_limits_for_tests
    settings.web_terminal_auth_secret = "login-secret"
    settings.web_terminal_disable_auth_for_tests = False
    settings.web_terminal_disable_security_rate_limits_for_tests = False
    monkeypatch.setattr(captcha_service, "_random_code", lambda: "ABCDE")
    await reset_security_store_for_tests()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            failures = [
                await client.post("/api/auth/login", json={"secret": "wrong"})
                for _ in range(4)
            ]
            limited = await client.post("/api/auth/login", json={"secret": "wrong"})
            still_limited = await client.post("/api/auth/login", json={"secret": "login-secret"})
            captcha = await client.post("/api/auth/captcha")
            captcha_body = captcha.json()
            accepted = await client.post(
                "/api/auth/login",
                json={
                    "secret": "login-secret",
                    "captcha_id": captcha_body["captcha_id"],
                    "captcha_answer": "abcde",
                },
            )
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable
        settings.web_terminal_disable_security_rate_limits_for_tests = previous_limits
        await reset_security_store_for_tests()

    assert [response.status_code for response in failures] == [401, 401, 401, 401]
    assert limited.status_code == 429
    assert limited.json()["code"] == "captcha_required"
    assert limited.headers["retry-after"].isdigit()
    assert still_limited.status_code == 429
    assert captcha.status_code == 200
    assert captcha_body["image_base64"].startswith("iVBORw0KGgo")
    assert accepted.status_code == 200
    assert accepted.json()["token"].startswith("wtauth.")


@pytest.mark.asyncio
async def test_captcha_endpoint_is_hidden_when_auth_disabled():
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    settings.web_terminal_auth_secret = None
    settings.web_terminal_disable_auth_for_tests = False
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/auth/captcha")
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_http_auth_rejects_session_token_query_param():
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    settings.web_terminal_auth_secret = "login-secret"
    settings.web_terminal_disable_auth_for_tests = False
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post("/api/auth/login", json={"secret": "login-secret"})
            token = login.json()["token"]
            rejected = await client.get(f"/api/missing-route?auth_token={token}")
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable

    assert rejected.status_code == 401


def test_ui_events_legacy_query_token_connection_is_parked_without_subscription():
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    settings.web_terminal_auth_secret = "login-secret"
    settings.web_terminal_disable_auth_for_tests = False
    try:
        token = create_session_token()
        test_app = _websocket_auth_test_app()
        hub = test_app.state.ui_event_hub
        with TestClient(test_app) as client:
            with client.websocket_connect(f"/api/ui-events?auth_token={token}") as websocket:
                assert websocket.receive_json() == {
                    "type": "auth_query_token_unsupported",
                    "reason": "reload_required",
                }
                assert hub._subscribers == set()
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable


def test_ui_events_rejects_invalid_session_token_query_param():
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    settings.web_terminal_auth_secret = "login-secret"
    settings.web_terminal_disable_auth_for_tests = False
    try:
        with TestClient(_websocket_auth_test_app()) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect("/api/ui-events?auth_token=not-valid") as websocket:
                    websocket.receive_json()
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable

    assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION


def test_websocket_auth_accepts_authorization_header():
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    settings.web_terminal_auth_secret = "login-secret"
    settings.web_terminal_disable_auth_for_tests = False
    try:
        token = create_session_token()
        with TestClient(_websocket_auth_test_app()) as client:
            with client.websocket_connect(
                "/api/ui-events",
                headers={"Authorization": f"Bearer {token}"},
            ) as websocket:
                assert websocket.receive_json() == {"type": "connected", "seq": 0}
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable


def test_websocket_auth_accepts_auth_subprotocol():
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    settings.web_terminal_auth_secret = "login-secret"
    settings.web_terminal_disable_auth_for_tests = False
    try:
        token = create_session_token()
        with TestClient(_websocket_auth_test_app()) as client:
            with client.websocket_connect(
                "/api/ui-events",
                subprotocols=[f"web-terminal-auth.{token}"],
            ) as websocket:
                assert websocket.receive_json() == {"type": "connected", "seq": 0}
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable


@pytest.mark.asyncio
async def test_registration_script_is_public_when_secret_configured():
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    settings.web_terminal_auth_secret = "login-secret"
    settings.web_terminal_disable_auth_for_tests = False
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/clients/register-script")
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable

    assert response.status_code == 200
    assert "WEB_TERMINAL_REGISTRATION_KEY" in response.text


@pytest.mark.asyncio
async def test_mcp_acp_routes_require_mcp_token_not_browser_session_token():
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    settings.web_terminal_auth_secret = "login-secret"
    settings.web_terminal_disable_auth_for_tests = False
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post("/api/auth/login", json={"secret": "login-secret"})
            browser_token = login.json()["token"]
            mcp_token = create_mcp_token(
                source_client_id="11111111-1111-1111-1111-111111111111",
                source_window_id="22222222-2222-2222-2222-222222222222",
            )
            no_token = await client.get("/api/mcp/acp/missing")
            browser_rejected = await client.get(
                "/api/mcp/acp/missing",
                headers={"Authorization": f"Bearer {browser_token}"},
            )
            mcp_allowed_to_route = await client.get(
                "/api/mcp/acp/missing",
                headers={"Authorization": f"Bearer {mcp_token}"},
            )
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable

    assert no_token.status_code == 401
    assert browser_rejected.status_code == 401
    assert browser_rejected.json()["detail"] == "mcp token required"
    assert mcp_allowed_to_route.status_code == 404


@pytest.mark.asyncio
async def test_agent_ops_routes_require_agent_ops_token_not_browser_session_token():
    settings = get_settings()
    previous_secret = settings.web_terminal_auth_secret
    previous_disable = settings.web_terminal_disable_auth_for_tests
    settings.web_terminal_auth_secret = "login-secret"
    settings.web_terminal_disable_auth_for_tests = False
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post("/api/auth/login", json={"secret": "login-secret"})
            browser_token = login.json()["token"]
            ops_token = create_agent_ops_token(
                source_client_id="11111111-1111-1111-1111-111111111111",
                source_window_id="22222222-2222-2222-2222-222222222222",
            )
            no_token = await client.get("/api/agent-ops/missing")
            browser_rejected = await client.get(
                "/api/agent-ops/missing",
                headers={"Authorization": f"Bearer {browser_token}"},
            )
            ops_allowed_to_route = await client.get(
                "/api/agent-ops/missing",
                headers={"Authorization": f"Bearer {ops_token}"},
            )
    finally:
        settings.web_terminal_auth_secret = previous_secret
        settings.web_terminal_disable_auth_for_tests = previous_disable

    assert no_token.status_code == 401
    assert browser_rejected.status_code == 401
    assert browser_rejected.json()["detail"] == "agent ops token required"
    assert ops_allowed_to_route.status_code == 404
