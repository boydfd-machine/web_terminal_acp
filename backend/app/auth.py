from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import urlopen
from uuid import UUID

from fastapi import Request, WebSocket, status
from fastapi.responses import JSONResponse
import jwt
from jwt import InvalidTokenError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import get_settings
from app.db import SessionLocal
from app.platform.auth_context import AuthIdentity, auth_identity_context
from app.platform.keycloak import keycloak_config, keycloak_enabled
from app.platform.request_path import request_scope_path
from app.platform.user_repository import upsert_user_for_identity

AUTH_LOGIN_PATH = "/api/auth/login"
AUTH_CAPTCHA_PATH = "/api/auth/captcha"
AUTH_STATUS_PATH = "/api/auth/status"
AUTH_REFRESH_PATH = "/api/auth/refresh"
AUTH_KEYCLOAK_CALLBACK_PATH = "/api/auth/keycloak/callback"
CLIENT_REGISTRATION_PATH = "/api/clients/register"
CLIENT_REGISTRATION_SCRIPT_PATH = "/api/clients/register-script"
HEALTH_PATH = "/healthz"
MCP_ACP_API_PREFIX = "/api/mcp/acp"
AGENT_OPS_API_PREFIX = "/api/agent-ops"
_TOKEN_PREFIX = "wtauth"
_MCP_TOKEN_PREFIX = "wtmcp"
_MCP_TOKEN_SCOPE = "acp"
_WEBSOCKET_AUTH_PROTOCOL_PREFIX = "web-terminal-auth."
_JWKS_CACHE: dict[str, tuple[float, dict[str, object]]] = {}


@dataclass(frozen=True)
class McpTokenClaims:
    source_client_id: UUID
    source_window_id: UUID
    issued_at: int


def auth_enabled() -> bool:
    if get_settings().web_terminal_disable_auth_for_tests:
        return False
    return bool((get_settings().web_terminal_auth_secret or "").strip()) or keycloak_enabled(
        get_settings()
    )


def _auth_secret() -> str:
    secret = (get_settings().web_terminal_auth_secret or "").strip()
    if not secret and keycloak_enabled(get_settings()):
        secret = (get_settings().keycloak_client_secret or "").strip()
    if not secret:
        raise RuntimeError("WEB_TERMINAL_AUTH_SECRET or KEYCLOAK_CLIENT_SECRET is not configured")
    return secret


def _password_auth_secret() -> str:
    secret = (get_settings().web_terminal_auth_secret or "").strip()
    if not secret:
        raise RuntimeError("WEB_TERMINAL_AUTH_SECRET is not configured")
    return secret


def _session_ttl_seconds() -> int:
    ttl = get_settings().web_terminal_auth_session_ttl_seconds
    return max(ttl, 1)


def _sign(message: str) -> str:
    return hmac.new(_auth_secret().encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_internal_message(message: str) -> str:
    return _sign(message)


def create_session_token(now: int | None = None) -> str:
    if keycloak_enabled(get_settings()):
        raise RuntimeError("password session tokens are disabled when Keycloak is configured")
    issued_at = int(time.time()) if now is None else now
    nonce = secrets.token_urlsafe(24)
    body = f"{issued_at}.{nonce}"
    return f"{_TOKEN_PREFIX}.{body}.{_sign(body)}"


def create_mcp_token(
    *,
    source_client_id: UUID | str,
    source_window_id: UUID | str,
    now: int | None = None,
) -> str:
    issued_at = int(time.time()) if now is None else now
    nonce = secrets.token_urlsafe(24)
    body = f"{_MCP_TOKEN_SCOPE}.{source_client_id}.{source_window_id}.{issued_at}.{nonce}"
    return f"{_MCP_TOKEN_PREFIX}.{body}.{_sign(body)}"


def create_agent_ops_token(
    *,
    source_client_id: UUID | str,
    source_window_id: UUID | str,
    now: int | None = None,
) -> str:
    return create_mcp_token(
        source_client_id=source_client_id,
        source_window_id=source_window_id,
        now=now,
    )


def verify_login_secret(secret: str) -> bool:
    if keycloak_enabled(get_settings()):
        return False
    configured = _password_auth_secret()
    return hmac.compare_digest(secret, configured)


def verify_session_token(token: str, now: int | None = None) -> bool:
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != _TOKEN_PREFIX:
        return False
    issued_at_text, nonce, signature = parts[1], parts[2], parts[3]
    if not issued_at_text or not nonce or not signature:
        return False
    body = f"{issued_at_text}.{nonce}"
    if not hmac.compare_digest(signature, _sign(body)):
        return False
    try:
        issued_at = int(issued_at_text)
    except ValueError:
        return False
    current_time = int(time.time()) if now is None else now
    if issued_at > current_time + 60:
        return False
    return current_time - issued_at <= _session_ttl_seconds()


def verify_browser_token(token: str, now: int | None = None) -> AuthIdentity | None:
    if keycloak_enabled(get_settings()):
        return verify_keycloak_token(token)
    if verify_session_token(token, now=now):
        return AuthIdentity(user_id="local", auth_provider="local")
    return None


def _is_browser_token_authenticated(token: str | None) -> bool:
    if token is None:
        return False
    return verify_browser_token(token) is not None


def verify_keycloak_token(token: str) -> AuthIdentity | None:
    config = keycloak_config(get_settings())
    if config is None:
        return None
    try:
        claims = jwt.decode(
            token,
            _keycloak_verification_key(token),
            algorithms=["RS256"],
            issuer=config.issuer,
            options={"require": ["sub", "iss", "exp"], "verify_aud": False},
        )
    except (InvalidTokenError, RuntimeError, ValueError):
        return None
    if not _keycloak_claims_match_client(claims, config.client_id):
        return None
    subject = str(claims.get("sub") or "").strip()
    if not subject:
        return None
    return AuthIdentity(
        user_id=subject,
        username=_optional_claim(claims, "preferred_username"),
        email=_optional_claim(claims, "email"),
        display_name=_optional_claim(claims, "name"),
        auth_provider="keycloak",
    )


def _keycloak_claims_match_client(claims: dict[str, object], client_id: str) -> bool:
    audience = claims.get("aud")
    if isinstance(audience, str) and audience == client_id:
        return True
    if isinstance(audience, list) and client_id in {str(value) for value in audience}:
        return True
    authorized_party = claims.get("azp")
    if isinstance(authorized_party, str) and authorized_party == client_id:
        return True
    token_client_id = claims.get("client_id")
    return isinstance(token_client_id, str) and token_client_id == client_id


def _optional_claim(claims: dict[str, object], name: str) -> str | None:
    value = claims.get(name)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _keycloak_verification_key(token: str) -> object:
    config = keycloak_config(get_settings())
    if config is None:
        raise RuntimeError("Keycloak is not configured")
    if config.public_key_pem:
        return config.public_key_pem
    jwks = _cached_keycloak_jwks(config.jwks_uri)
    header = jwt.get_unverified_header(token)
    key_id = str(header.get("kid") or "")
    for key in jwt.PyJWKSet.from_dict(jwks).keys:
        if key.key_id == key_id:
            return key.key
    raise RuntimeError("Keycloak signing key not found")


def _cached_keycloak_jwks(jwks_uri: str) -> dict[str, object]:
    now = time.monotonic()
    cached = _JWKS_CACHE.get(jwks_uri)
    ttl = get_settings().keycloak_jwks_cache_ttl_seconds
    if cached is not None and now - cached[0] <= ttl:
        return cached[1]
    try:
        with urlopen(jwks_uri, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise RuntimeError("failed to fetch Keycloak JWKS") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("invalid Keycloak JWKS")
    _JWKS_CACHE[jwks_uri] = (now, payload)
    return payload


def verify_mcp_token(token: str, now: int | None = None) -> McpTokenClaims | None:
    parts = token.split(".")
    if len(parts) != 7 or parts[0] != _MCP_TOKEN_PREFIX:
        return None
    scope, source_client_id, source_window_id, issued_at_text, nonce, signature = parts[1:]
    if scope != _MCP_TOKEN_SCOPE or not nonce or not signature:
        return None
    body = ".".join(parts[1:6])
    if not hmac.compare_digest(signature, _sign(body)):
        return None
    try:
        issued_at = int(issued_at_text)
        client_id = UUID(source_client_id)
        window_id = UUID(source_window_id)
    except ValueError:
        return None
    current_time = int(time.time()) if now is None else now
    if issued_at > current_time + 60:
        return None
    if current_time - issued_at > _session_ttl_seconds():
        return None
    return McpTokenClaims(
        source_client_id=client_id,
        source_window_id=window_id,
        issued_at=issued_at,
    )


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        return None
    return token


def _request_token(request: Request) -> str | None:
    return _bearer_token(request.headers.get("authorization"))


def _websocket_subprotocol_token(sec_websocket_protocol: str | None) -> str | None:
    if sec_websocket_protocol is None:
        return None
    for protocol in sec_websocket_protocol.split(","):
        protocol = protocol.strip()
        if not protocol.startswith(_WEBSOCKET_AUTH_PROTOCOL_PREFIX):
            continue
        token = protocol.removeprefix(_WEBSOCKET_AUTH_PROTOCOL_PREFIX)
        if token:
            return token
    return None


def websocket_session_token(websocket: WebSocket) -> str | None:
    return _bearer_token(websocket.headers.get("authorization")) or _websocket_subprotocol_token(
        websocket.headers.get("sec-websocket-protocol")
    )


def websocket_auth_subprotocol(websocket: WebSocket) -> str | None:
    """Extract auth subprotocol from WebSocket to pass to accept()."""
    token = _websocket_subprotocol_token(websocket.headers.get("sec-websocket-protocol"))
    return f"{_WEBSOCKET_AUTH_PROTOCOL_PREFIX}{token}" if token else None


def is_websocket_authenticated(websocket: WebSocket) -> bool:
    if not auth_enabled():
        return True
    token = websocket_session_token(websocket)
    return _is_browser_token_authenticated(token)


def websocket_auth_identity(websocket: WebSocket) -> AuthIdentity | None:
    token = websocket_session_token(websocket)
    return None if token is None else verify_browser_token(token)


async def require_websocket_auth(websocket: WebSocket) -> bool:
    if is_websocket_authenticated(websocket):
        return True
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return False


async def require_websocket_client_access(websocket: WebSocket, client_id: UUID) -> bool:
    if not auth_enabled():
        return True
    identity = websocket_auth_identity(websocket)
    if identity is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return False
    if identity.auth_provider != "keycloak":
        return True
    if await _identity_can_access_client(
        identity,
        client_id,
        getattr(websocket.app.state, "auth_session_factory", SessionLocal),
    ):
        return True
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return False


def _is_registration_callback(path: str) -> bool:
    return path in {CLIENT_REGISTRATION_PATH, CLIENT_REGISTRATION_SCRIPT_PATH}


def _is_client_update_callback(path: str) -> bool:
    if not path.startswith("/api/clients/"):
        return False
    return path.endswith("/update/package") or path.endswith("/update/complete")


def _is_mcp_acp_path(path: str) -> bool:
    return path == MCP_ACP_API_PREFIX or path.startswith(f"{MCP_ACP_API_PREFIX}/")


def _is_agent_ops_path(path: str) -> bool:
    return path == AGENT_OPS_API_PREFIX or path.startswith(f"{AGENT_OPS_API_PREFIX}/")


def _is_source_ops_path(path: str) -> bool:
    return _is_mcp_acp_path(path) or _is_agent_ops_path(path)


def _requires_http_auth(path: str) -> bool:
    if path in {
        HEALTH_PATH,
        AUTH_LOGIN_PATH,
        AUTH_CAPTCHA_PATH,
        AUTH_STATUS_PATH,
        AUTH_REFRESH_PATH,
        AUTH_KEYCLOAK_CALLBACK_PATH,
    }:
        return False
    if _is_registration_callback(path) or _is_client_update_callback(path):
        return False
    return path.startswith("/api/")


def _client_id_from_api_path(path: str) -> UUID | None:
    prefix = "/api/clients/"
    if not path.startswith(prefix):
        return None
    client_id_text = path.removeprefix(prefix).split("/", 1)[0]
    try:
        return UUID(client_id_text)
    except ValueError:
        return None


async def _identity_can_access_client(
    identity: AuthIdentity,
    client_id: UUID,
    session_factory=SessionLocal,
) -> bool:
    from app.contexts.clients.infrastructure.repository import get_client_for_owner

    async with session_factory() as session:
        user = await upsert_user_for_identity(session, identity)
        client = await get_client_for_owner(session, client_id, user.id)
        await session.commit()
        return client is not None


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        identity: AuthIdentity | None = None
        path = request_scope_path(request)
        if auth_enabled() and _requires_http_auth(path):
            token = _request_token(request)
            if _is_source_ops_path(path):
                if token is None or verify_mcp_token(token) is None:
                    detail = "mcp token required" if _is_mcp_acp_path(path) else "agent ops token required"
                    return JSONResponse(
                        {"detail": detail},
                        status_code=status.HTTP_401_UNAUTHORIZED,
                    )
            else:
                identity = None if token is None else verify_browser_token(token)
                if identity is None:
                    return JSONResponse(
                        {"detail": "login required"},
                        status_code=status.HTTP_401_UNAUTHORIZED,
                    )
                client_id = _client_id_from_api_path(path)
                if (
                    client_id is not None
                    and identity.auth_provider == "keycloak"
                    and not await _identity_can_access_client(
                        identity,
                        client_id,
                        getattr(request.app.state, "auth_session_factory", SessionLocal),
                    )
                ):
                    return JSONResponse(
                        {"detail": "client not found"},
                        status_code=status.HTTP_404_NOT_FOUND,
                    )
        with auth_identity_context(identity):
            return await call_next(request)


__all__ = [
    "AuthIdentity",
    "AuthMiddleware",
    "auth_enabled",
    "create_agent_ops_token",
    "create_mcp_token",
    "create_session_token",
    "require_websocket_client_access",
    "require_websocket_auth",
    "verify_browser_token",
]
