from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.contexts.workspace.api.project_file_search_schemas import ProjectFileSearchOut
from app.contexts.workspace.api.projects_routes import _broker_for_client, _require_client
from app.contexts.workspace.application.project_file_search import search_project_files
from app.contexts.workspace.application.project_files import ProjectPathError
from app.contexts.terminal_runtime.application.runtime_provider import (
    RemoteClientUnavailable,
    RemoteTerminalError,
)
from app.contexts.terminal_runtime.application.broker import TerminalRuntimeUnavailable

router = APIRouter(prefix="/api/clients/{client_id}/projects/files", tags=["projects"])

ProjectFileSearchQuery = Annotated[str, Query(alias="q", min_length=1, max_length=512)]
ProjectFileSearchLimit = Annotated[int, Query(ge=1, le=100)]
ProjectFileSearchOffset = Annotated[int, Query(ge=0)]
ProjectFileSearchMode = Literal["all", "content", "filename"]


@router.get("/search", response_model=ProjectFileSearchOut)
async def search_files(
    client_id: UUID,
    request: Request,
    q: ProjectFileSearchQuery,
    mode: ProjectFileSearchMode = Query("all"),
    project_path: str | None = Query(None, max_length=4096),
    limit: ProjectFileSearchLimit = 25,
    offset: ProjectFileSearchOffset = 0,
    session: AsyncSession = Depends(get_session),
) -> ProjectFileSearchOut:
    client = await _require_client(session, client_id)
    broker = _broker_for_client(request, client)
    try:
        return await search_project_files(
            session,
            broker,
            client_id=client_id,
            query=q,
            mode=mode,
            project_path=project_path,
            limit=limit,
            offset=offset,
        )
    except ProjectPathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RemoteClientUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"message": "remote client unavailable", "reason": exc.reason},
        ) from exc
    except RemoteTerminalError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except TerminalRuntimeUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
