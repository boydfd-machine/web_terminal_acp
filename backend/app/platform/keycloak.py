from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import Settings


@dataclass(frozen=True)
class KeycloakConfig:
    base_url: str
    realm: str
    client_id: str
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    end_session_endpoint: str
    public_key_pem: str | None
    client_secret: str | None


@dataclass(frozen=True)
class KeycloakTokenSet:
    access_token: str
    refresh_token: str


def keycloak_enabled(settings: Settings) -> bool:
    return bool(
        (settings.keycloak_base_url or "").strip()
        and (settings.keycloak_realm or "").strip()
        and (settings.keycloak_client_id or "").strip()
    )


def keycloak_config(settings: Settings) -> KeycloakConfig | None:
    if not keycloak_enabled(settings):
        return None
    base_url = settings.keycloak_base_url.strip().rstrip("/")
    realm = settings.keycloak_realm.strip()
    client_id = settings.keycloak_client_id.strip()
    realm_base = f"{base_url}/realms/{realm}"
    oidc_base = f"{realm_base}/protocol/openid-connect"
    return KeycloakConfig(
        base_url=base_url,
        realm=realm,
        client_id=client_id,
        issuer=realm_base,
        authorization_endpoint=f"{oidc_base}/auth",
        token_endpoint=f"{oidc_base}/token",
        jwks_uri=f"{oidc_base}/certs",
        end_session_endpoint=f"{oidc_base}/logout",
        public_key_pem=(settings.keycloak_public_key_pem or "").strip() or None,
        client_secret=(settings.keycloak_client_secret or "").strip() or None,
    )


def keycloak_public_config(config: KeycloakConfig | None) -> dict[str, str] | None:
    if config is None:
        return None
    return {
        "base_url": config.base_url,
        "realm": config.realm,
        "client_id": config.client_id,
        "issuer": config.issuer,
        "authorization_endpoint": config.authorization_endpoint,
        "token_endpoint": config.token_endpoint,
        "end_session_endpoint": config.end_session_endpoint,
    }


async def exchange_keycloak_authorization_code(
    config: KeycloakConfig,
    *,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> KeycloakTokenSet:
    payload = {
        "grant_type": "authorization_code",
        "client_id": config.client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    return await _exchange_keycloak_token(config, payload)


async def refresh_keycloak_token(
    config: KeycloakConfig,
    *,
    refresh_token: str,
) -> KeycloakTokenSet:
    payload = {
        "grant_type": "refresh_token",
        "client_id": config.client_id,
        "refresh_token": refresh_token,
    }
    return await _exchange_keycloak_token(
        config,
        payload,
        fallback_refresh_token=refresh_token,
    )


async def _exchange_keycloak_token(
    config: KeycloakConfig,
    payload: dict[str, str],
    *,
    fallback_refresh_token: str | None = None,
) -> KeycloakTokenSet:
    if config.client_secret:
        payload["client_secret"] = config.client_secret
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(config.token_endpoint, data=payload)
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ValueError("Keycloak token exchange failed") from exc
    access_token = body.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise ValueError("Keycloak access token missing")
    refresh_token = body.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        refresh_token = fallback_refresh_token
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        raise ValueError("Keycloak refresh token missing")
    return KeycloakTokenSet(access_token=access_token, refresh_token=refresh_token)
