from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.contexts.clients.api.schemas import (
    BootstrapClientIn,
    BootstrapClientOut,
    ClientRegistrationKeyCreateIn,
    ClientRegistrationKeyOut,
    ClientOut,
    ClientPatchIn,
    ClientUpdateCompleteIn,
    ClientUpdateOut,
    DirectClientRegisterIn,
    DirectClientRegisterOut,
)
from app.contexts.clients.application.api_service import ClientApiService
from app.contexts.clients.application.errors import ClientApiError
from app.contexts.clients.application.runners import (
    BootstrapRunner,
    UpdateRunner,
    default_bootstrap_runner,
    default_update_runner,
)
from app.contexts.clients.application.direct_registration_script import read_direct_registration_script
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry

router = APIRouter(prefix="/api/clients", tags=["clients"])


def get_bootstrap_runner() -> BootstrapRunner:
    return default_bootstrap_runner()


def get_update_runner() -> UpdateRunner:
    return default_update_runner()


def _connection_registry(request: Request) -> ClientConnectionRegistry:
    registry = getattr(request.app.state, "client_connections", None)
    if registry is None:
        registry = ClientConnectionRegistry()
        request.app.state.client_connections = registry
    return registry


def _service(request: Request, session: AsyncSession) -> ClientApiService:
    return ClientApiService(
        session,
        app_state=request.app.state,
        connection_registry=_connection_registry(request),
    )


def _raise_http(exc: ClientApiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get("", response_model=list[ClientOut])
async def read_clients(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[ClientOut] | Response:
    return await _service(request, session).list_clients_response()


@router.post("/bootstrap", response_model=BootstrapClientOut)
async def bootstrap_remote_client_route(
    request: Request,
    payload: BootstrapClientIn,
    session: AsyncSession = Depends(get_session),
    runner: BootstrapRunner = Depends(get_bootstrap_runner),
) -> BootstrapClientOut:
    return await bootstrap_remote_client(payload, session=session, runner=runner, request=request)


async def bootstrap_remote_client(
    payload: BootstrapClientIn,
    session: AsyncSession,
    runner: BootstrapRunner,
    request: Request | None = None,
) -> BootstrapClientOut:
    app_state = None if request is None else request.app.state
    try:
        return await ClientApiService(session, app_state=app_state).bootstrap_remote_client(
            payload,
            runner=runner,
        )
    except ClientApiError as exc:
        _raise_http(exc)


@router.post("/registration-keys", response_model=ClientRegistrationKeyOut)
async def create_client_registration_key(
    request: Request,
    payload: ClientRegistrationKeyCreateIn,
    session: AsyncSession = Depends(get_session),
) -> ClientRegistrationKeyOut:
    return await _service(request, session).create_registration_key(label=payload.label)


@router.get("/register-script", response_class=PlainTextResponse)
async def read_client_registration_script() -> PlainTextResponse:
    return PlainTextResponse(
        read_direct_registration_script(),
        media_type="text/x-shellscript; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="register-client-direct.sh"'},
    )


@router.post("/register", response_model=DirectClientRegisterOut)
async def register_client_directly(
    request: Request,
    payload: DirectClientRegisterIn,
    session: AsyncSession = Depends(get_session),
) -> DirectClientRegisterOut:
    try:
        return await _service(request, session).register_direct_client(
            registration_key=payload.registration_key,
            name=payload.name,
            hostname=payload.hostname,
            install_path=payload.install_path,
            server_url=payload.server_url,
        )
    except ClientApiError as exc:
        _raise_http(exc)


@router.post("/{client_id}/update", response_model=ClientUpdateOut, status_code=status.HTTP_202_ACCEPTED)
async def update_remote_client(
    client_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    runner: UpdateRunner = Depends(get_update_runner),
) -> ClientUpdateOut:
    try:
        return await _service(request, session).start_remote_client_update(client_id, runner=runner)
    except ClientApiError as exc:
        _raise_http(exc)


@router.get("/{client_id}/update/package")
async def read_client_update_package(
    request: Request,
    client_id: UUID,
    job_id: str | None = None,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    try:
        return await _service(request, session).read_update_package(
            client_id,
            job_id=job_id,
            authorization=authorization,
        )
    except ClientApiError as exc:
        _raise_http(exc)


@router.post("/{client_id}/update/complete")
async def complete_client_update(
    request: Request,
    client_id: UUID,
    payload: ClientUpdateCompleteIn,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    try:
        return await _service(request, session).complete_client_update(
            client_id,
            payload,
            authorization=authorization,
        )
    except ClientApiError as exc:
        _raise_http(exc)


@router.get("/{client_id}", response_model=ClientOut)
async def read_client(
    request: Request,
    client_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ClientOut:
    try:
        return await _service(request, session).read_client(client_id)
    except ClientApiError as exc:
        _raise_http(exc)


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client(
    request: Request,
    client_id: UUID,
    payload: ClientPatchIn,
    session: AsyncSession = Depends(get_session),
) -> ClientOut:
    try:
        return await _service(request, session).update_client(client_id, payload)
    except ClientApiError as exc:
        _raise_http(exc)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    request: Request,
    client_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        await _service(request, session).delete_client(client_id)
    except ClientApiError as exc:
        _raise_http(exc)
