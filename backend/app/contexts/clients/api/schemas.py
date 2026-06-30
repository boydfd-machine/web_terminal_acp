from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.platform.common_schemas import (
    BootstrapHost,
    BootstrapPrivateKey,
    BootstrapServerUrl,
    BootstrapUsername,
    ClientName,
    ClientRuntimeOut,
    ClientStatusOut,
    RegistrationKey,
)
from app.platform.auth_schemas import (
    AuthStatusOut,
    CaptchaOut,
    KeycloakPublicConfigOut,
    LoginIn,
    LoginOut,
)

class BootstrapClientIn(BaseModel):
    name: ClientName
    host: BootstrapHost
    port: int = Field(ge=1, le=65535)
    username: BootstrapUsername
    private_key: BootstrapPrivateKey
    passphrase: str | None = None
    server_url: BootstrapServerUrl


class BootstrapClientOut(BaseModel):
    client_id: UUID
    name: str
    status: ClientStatusOut
    reused: bool


class ClientRegistrationKeyCreateIn(BaseModel):
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None


class ClientRegistrationKeyOut(BaseModel):
    id: UUID
    key: str
    label: str | None = None
    created_at: datetime | None = None


class DirectClientRegisterIn(BaseModel):
    registration_key: RegistrationKey
    name: ClientName
    hostname: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None
    install_path: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)] | None = None
    server_url: BootstrapServerUrl


class DirectClientRegisterOut(BaseModel):
    client_id: UUID
    token: str
    name: str
    config: dict[str, Any]
    package: dict[str, Any]


class ClientUpdateOut(BaseModel):
    client_id: UUID
    job_id: str
    status: Literal["STARTED"]
    method: str


class ClientOut(BaseModel):
    id: UUID
    name: str
    status: ClientStatusOut
    hostname: str | None
    install_path: str | None
    version: str | None
    last_update_at: datetime | None
    runtime: ClientRuntimeOut
    last_seen_at: datetime | None
    connected_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ClientPatchIn(BaseModel):
    name: ClientName | None = None


class ClientUpdateCompleteIn(BaseModel):
    job_id: str | None = None
