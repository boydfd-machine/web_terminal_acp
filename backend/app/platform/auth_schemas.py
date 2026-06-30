from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.platform.common_schemas import CaptchaAnswer, CaptchaId, LoginSecret, RefreshToken


class LoginIn(BaseModel):
    secret: LoginSecret
    captcha_id: CaptchaId | None = None
    captcha_answer: CaptchaAnswer | None = None

    @field_validator("captcha_id", "captcha_answer", mode="before")
    @classmethod
    def _blank_to_none(cls, value):
        if value is None or isinstance(value, str) and value.strip() == "":
            return None
        return value


class LoginOut(BaseModel):
    token: str
    refresh_token: str | None = None
    enabled: bool = True


class RefreshTokenIn(BaseModel):
    refresh_token: RefreshToken


class KeycloakCallbackIn(BaseModel):
    code: str
    redirect_uri: str
    code_verifier: str


class KeycloakPublicConfigOut(BaseModel):
    base_url: str
    realm: str
    client_id: str
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    end_session_endpoint: str


class AuthStatusOut(BaseModel):
    enabled: bool
    mode: str = "disabled"
    keycloak: KeycloakPublicConfigOut | None = None


class CaptchaOut(BaseModel):
    captcha_id: str
    image_base64: str
    ttl_seconds: int
