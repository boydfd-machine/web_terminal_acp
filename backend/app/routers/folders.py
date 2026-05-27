import json
from time import monotonic
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Client, Folder, VirtualWindow
from app.repositories.clients import ensure_local_client, get_client
from app.repositories.folders import build_tree, get_or_create_folder_by_path
from app.routers.ui_events import ui_event_hub_from_state
from app.schemas import ClientWindowsActivityOut, FolderCreateIn, FolderOut, TreeFolderOut
from app.services.window_activity_api import load_client_windows_activity

router = APIRouter(prefix="/api", tags=["folders"])
_RESPONSE_CACHE_TTL_SECONDS = 10.0
_response_cache: dict[tuple[object, ...], tuple[float, str]] = {}


async def _require_client(session: AsyncSession, client_id: UUID) -> Client:
    client = await get_client(session, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
    return client


@router.get("/clients/{client_id}/tree", response_model=list[TreeFolderOut], response_model_exclude_none=True)
async def get_client_tree(client_id: UUID, session: AsyncSession = Depends(get_session)):
    await _require_client(session, client_id)
    cache_key = ("tree", client_id, await _tree_cache_fingerprint(session, client_id))
    cached = _cached_response(cache_key)
    if cached is not None:
        return cached
    tree = await build_tree(session, client_id)
    return _store_response(cache_key, tree)


@router.get(
    "/clients/{client_id}/windows/activity",
    response_model=ClientWindowsActivityOut,
    response_model_exclude_none=True,
)
async def get_client_windows_activity(
    client_id: UUID,
    include_runtime_tags: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
) -> ClientWindowsActivityOut | Response:
    await _require_client(session, client_id)
    cache_key = (
        "activity",
        client_id,
        include_runtime_tags,
        await _tree_cache_fingerprint(session, client_id),
    )
    cached = _cached_response(cache_key)
    if cached is not None:
        return cached
    activity = await load_client_windows_activity(
        session,
        client_id,
        include_runtime_tags=include_runtime_tags,
    )
    return _store_response(cache_key, activity)


@router.get("/tree", response_model=list[TreeFolderOut], response_model_exclude_none=True)
async def get_tree(session: AsyncSession = Depends(get_session)):
    client = await ensure_local_client(session)
    cache_key = ("tree", client.id, await _tree_cache_fingerprint(session, client.id))
    cached = _cached_response(cache_key)
    if cached is not None:
        return cached
    tree = await build_tree(session, client.id)
    await session.commit()
    return _store_response(cache_key, tree)


async def _get_or_create_folder_and_commit(session: AsyncSession, client_id: UUID, path: str):
    folder = await get_or_create_folder_by_path(session, client_id, path)
    await session.commit()
    return folder


async def _create_folder_for_client(
    session: AsyncSession, client_id: UUID, payload: FolderCreateIn
) -> FolderOut:
    try:
        folder = await _get_or_create_folder_and_commit(session, client_id, payload.path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError:
        await session.rollback()
        try:
            folder = await _get_or_create_folder_and_commit(session, client_id, payload.path)
        except IntegrityError as retry_exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="folder path conflict; retry request",
            ) from retry_exc
        except ValueError as retry_exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(retry_exc),
            ) from retry_exc
    return FolderOut(id=folder.id, name=folder.name, path=folder.path)


async def _tree_window_ids(session: AsyncSession, client_id: UUID) -> tuple[UUID, ...]:
    return tuple(
        await session.scalars(
            select(VirtualWindow.id)
            .where(
                VirtualWindow.client_id == client_id,
                VirtualWindow.folder_id.is_not(None),
            )
            .order_by(VirtualWindow.id)
        )
    )


async def _tree_window_fingerprint(
    session: AsyncSession, client_id: UUID
) -> tuple[tuple[UUID, UUID | None], ...]:
    rows = await session.execute(
        select(VirtualWindow.id, VirtualWindow.folder_id)
        .where(
            VirtualWindow.client_id == client_id,
            VirtualWindow.folder_id.is_not(None),
        )
        .order_by(VirtualWindow.id)
    )
    return tuple(rows)


async def _tree_cache_fingerprint(
    session: AsyncSession, client_id: UUID
) -> tuple[tuple[object, ...], ...]:
    folder_rows = await session.execute(
        select(Folder.path, Folder.id, Folder.parent_id)
        .where(Folder.client_id == client_id)
        .order_by(Folder.path, Folder.id)
    )
    window_rows = await _tree_window_fingerprint(session, client_id)
    return tuple(
        ("folder", path, folder_id, parent_id)
        for path, folder_id, parent_id in folder_rows
    ) + tuple(("window", window_id, folder_id) for window_id, folder_id in window_rows)


def _cached_response(cache_key: tuple[object, ...]) -> Response | None:
    cached = _response_cache.get(cache_key)
    if cached is None:
        return None
    created_at, content = cached
    if monotonic() - created_at > _RESPONSE_CACHE_TTL_SECONDS:
        _response_cache.pop(cache_key, None)
        return None
    return Response(content=content, media_type="application/json")


def _store_response(cache_key: tuple[object, ...], payload: object) -> Response:
    content = json.dumps(_response_payload(payload), separators=(",", ":"))
    _response_cache[cache_key] = (monotonic(), content)
    return Response(content=content, media_type="application/json")


def _response_payload(payload: object) -> object:
    if isinstance(payload, BaseModel):
        return jsonable_encoder(payload.model_dump(exclude_none=True))
    return jsonable_encoder(payload, exclude_none=True)


@router.post("/clients/{client_id}/folders", response_model=FolderOut)
async def create_client_folder(
    request: Request,
    client_id: UUID,
    payload: FolderCreateIn,
    session: AsyncSession = Depends(get_session),
):
    await _require_client(session, client_id)
    folder = await _create_folder_for_client(session, client_id, payload)
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["tree"],
        client_id=client_id,
        reason="folder_created",
    )
    return folder


@router.post("/folders", response_model=FolderOut)
async def create_folder(
    request: Request,
    payload: FolderCreateIn,
    session: AsyncSession = Depends(get_session),
):
    client = await ensure_local_client(session)
    folder = await _create_folder_for_client(session, client.id, payload)
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["tree"],
        client_id=client.id,
        reason="folder_created",
    )
    return folder
