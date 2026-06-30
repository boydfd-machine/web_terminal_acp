from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.auth import auth_enabled, create_session_token, verify_keycloak_token, verify_login_secret
from app.config import get_settings
from app.platform.auth_schemas import (
    AuthStatusOut,
    CaptchaOut,
    KeycloakCallbackIn,
    LoginIn,
    LoginOut,
    RefreshTokenIn,
)
from app.platform.captcha_service import create_captcha_challenge, verify_captcha
from app.platform.keycloak import (
    exchange_keycloak_authorization_code,
    keycloak_config,
    keycloak_public_config,
    refresh_keycloak_token,
)
from app.platform.security_rate_limit import (
    clear_failed_login,
    client_ip_from_request,
    increment_failed_login,
    login_requires_captcha,
    rate_limit_response,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatusOut)
async def read_auth_status() -> AuthStatusOut:
    config = keycloak_config(get_settings())
    if config is not None:
        return AuthStatusOut(
            enabled=auth_enabled(),
            mode="keycloak",
            keycloak=keycloak_public_config(config),
        )
    if auth_enabled():
        return AuthStatusOut(enabled=True, mode="password")
    return AuthStatusOut(enabled=False, mode="disabled")


@router.post("/login", response_model=LoginOut, response_model_exclude_none=True)
async def login(request: Request, payload: LoginIn) -> LoginOut | Response:
    if not auth_enabled():
        return LoginOut(token="", enabled=False)
    if keycloak_config(get_settings()) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="password login disabled")

    client_ip = client_ip_from_request(request)
    captcha_required, retry_after = await login_requires_captcha(client_ip)
    if captcha_required and not await verify_captcha(
        payload.captcha_id,
        payload.captcha_answer,
        client_ip,
    ):
        return JSONResponse(
            {
                "detail": "captcha required",
                "code": "captcha_required",
                "retry_after_seconds": retry_after,
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
        )
    if not verify_login_secret(payload.secret):
        result = await increment_failed_login(client_ip)
        if not result.allowed:
            return rate_limit_response(result, "captcha required", code="captcha_required")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid login secret")
    await clear_failed_login(client_ip)
    return LoginOut(token=create_session_token(), enabled=True)


@router.post("/keycloak/callback", response_model=LoginOut, response_model_exclude_none=True)
async def keycloak_callback(payload: KeycloakCallbackIn) -> LoginOut:
    config = keycloak_config(get_settings())
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="keycloak disabled")
    try:
        token_set = await exchange_keycloak_authorization_code(
            config,
            code=payload.code,
            redirect_uri=payload.redirect_uri,
            code_verifier=payload.code_verifier,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="keycloak login failed",
        ) from exc
    return _keycloak_login_out(token_set, invalid_detail="invalid keycloak token")


@router.post("/refresh", response_model=LoginOut, response_model_exclude_none=True)
async def refresh_auth_token(payload: RefreshTokenIn) -> LoginOut:
    config = keycloak_config(get_settings())
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="keycloak disabled")
    try:
        token_set = await refresh_keycloak_token(
            config,
            refresh_token=payload.refresh_token,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh token invalid",
        ) from exc
    return _keycloak_login_out(token_set, invalid_detail="refresh token invalid")


def _keycloak_login_out(token_set, *, invalid_detail: str) -> LoginOut:
    access_token = _token_set_value(token_set, "access_token")
    refresh_token = _token_set_value(token_set, "refresh_token")
    if access_token is None or refresh_token is None or verify_keycloak_token(access_token) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=invalid_detail,
        )
    return LoginOut(token=access_token, refresh_token=refresh_token, enabled=True)


def _token_set_value(token_set, name: str) -> str | None:
    value = token_set.get(name) if isinstance(token_set, dict) else getattr(token_set, name, None)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


@router.post("/captcha", response_model=CaptchaOut)
async def create_auth_captcha(request: Request) -> CaptchaOut:
    if not auth_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="auth disabled")
    challenge = await create_captcha_challenge(client_ip_from_request(request))
    return CaptchaOut(
        captcha_id=challenge.captcha_id,
        image_base64=base64.b64encode(challenge.image_png).decode("ascii"),
        ttl_seconds=challenge.ttl_seconds,
    )
