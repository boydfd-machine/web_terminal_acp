from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from uuid import UUID

from fastapi import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contexts.clients.application.client_lookup import ensure_local_client, get_client
from app.contexts.workspace.api.schemas import FolderOut
from app.contexts.workspace.domain.folders import FolderProjectPathFilter
from app.contexts.workspace.infrastructure.folders_repository import (
    build_tree,
    get_or_create_folder_by_path,
    list_terminal_projects,
)
from app.contexts.activity.domain.terminal_time_range import TerminalTimeRange
from app.models import Client, Folder
from app.platform.polling_response_cache import (
    begin_response_cache_build,
    begin_response_cache_refresh,
    cached_or_stale_json_response_async,
    finish_response_cache_build,
    finish_response_cache_refresh,
    response_cache_scope,
    store_json_response_async,
)
from app.contexts.activity.application.window_activity import load_client_windows_activity

logger = logging.getLogger(__name__)


class FolderApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class FolderReadScope:
    client_id: UUID
    require_existing_client: bool
    time_range: TerminalTimeRange
    project_path: FolderProjectPathFilter = FolderProjectPathFilter(None)

    @classmethod
    def client_tree(
        cls,
        *,
        client_id: UUID,
        time_range: str | None,
        project_path: str | None,
    ) -> "FolderReadScope":
        return cls(
            client_id=client_id,
            require_existing_client=True,
            time_range=TerminalTimeRange(time_range),
            project_path=FolderProjectPathFilter.from_query(project_path),
        )

    @classmethod
    def client_terminal_projects(
        cls,
        *,
        client_id: UUID,
        time_range: str | None,
    ) -> "FolderReadScope":
        return cls(
            client_id=client_id,
            require_existing_client=True,
            time_range=TerminalTimeRange(time_range),
        )

    @classmethod
    def client_activity(
        cls,
        *,
        client_id: UUID,
        time_range: str | None,
        project_path: str | None,
    ) -> "FolderReadScope":
        return cls.client_tree(
            client_id=client_id,
            time_range=time_range,
            project_path=project_path,
        )

    def visible_since(self) -> datetime | None:
        return self.time_range.visible_since()


class FolderApiService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        refresh_session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session = session
        self._refresh_session_factory = refresh_session_factory

    async def get_tree(self, scope: FolderReadScope) -> Response:
        cache_key = self._tree_cache_key(scope)
        return await self._cached_response(
            cache_key,
            lambda session: self._build_tree_response(session, scope, cache_key),
            validate_on_miss=lambda: self._require_client(scope.client_id),
        )

    async def get_terminal_projects(self, scope: FolderReadScope) -> Response:
        cache_key = self._terminal_projects_cache_key(scope)
        return await self._cached_response(
            cache_key,
            lambda session: self._build_terminal_projects_response(session, scope, cache_key),
            validate_on_miss=lambda: self._require_client(scope.client_id),
        )

    async def get_windows_activity(
        self,
        scope: FolderReadScope,
        *,
        include_runtime_tags: bool,
    ) -> Response:
        cache_key = self._activity_cache_key(scope, include_runtime_tags)
        return await self._cached_response(
            cache_key,
            lambda session: self._build_activity_response(
                session,
                scope,
                include_runtime_tags=include_runtime_tags,
                cache_key=cache_key,
            ),
            validate_on_miss=lambda: self._require_client(scope.client_id),
        )

    async def get_local_tree(
        self,
        *,
        time_range: str | None,
        project_path: str | None,
    ) -> Response:
        client = await ensure_local_client(self._session)
        scope = FolderReadScope(
            client_id=client.id,
            require_existing_client=False,
            time_range=TerminalTimeRange(time_range),
            project_path=FolderProjectPathFilter.from_query(project_path),
        )
        cache_key = self._tree_cache_key(scope)
        return await self._cached_response(
            cache_key,
            lambda session: self._build_tree_response(session, scope, cache_key),
            on_store=lambda: self._session.commit(),
        )

    async def create_folder_for_client(self, client_id: UUID, path: str) -> FolderOut:
        await self._require_client(client_id)
        folder = await self._create_folder(client_id, path)
        return folder_out(folder)

    async def create_local_folder(self, path: str) -> tuple[UUID, FolderOut]:
        client = await ensure_local_client(self._session)
        folder = await self._create_folder(client.id, path)
        return client.id, folder_out(folder)

    async def _cached_response(
        self,
        cache_key: tuple[object, ...],
        build_response: Callable[[AsyncSession], Awaitable[Response]],
        *,
        validate_on_miss: Callable[[], Awaitable[object]] | None = None,
        on_store: Callable[[], Awaitable[object]] | None = None,
    ) -> Response:
        cached = await cached_or_stale_json_response_async(cache_key)
        if cached is not None and not cached.expired:
            return cached.response
        if cached is not None:
            self._refresh_response_cache(cache_key, build_response)
            return cached.response

        active_build = begin_response_cache_build(cache_key)
        if active_build is not None:
            await active_build
            cached = await cached_or_stale_json_response_async(cache_key)
            if cached is not None:
                return cached.response

        error: BaseException | None = None
        try:
            if validate_on_miss is not None:
                await validate_on_miss()
            response = await build_response(self._session)
            if on_store is not None:
                await on_store()
            return response
        except BaseException as exc:
            error = exc
            raise
        finally:
            finish_response_cache_build(cache_key, error)

    def _refresh_response_cache(
        self,
        cache_key: tuple[object, ...],
        refresh: Callable[[AsyncSession], Awaitable[Response]],
    ) -> None:
        if self._refresh_session_factory is None:
            return
        if not begin_response_cache_refresh(cache_key):
            return

        async def refresh_task() -> None:
            try:
                async with self._refresh_session_factory() as refresh_session:
                    await refresh(refresh_session)
            except Exception:
                logger.exception(
                    "polling response cache refresh failed",
                    extra={"cache_key": repr(cache_key)},
                )
            finally:
                finish_response_cache_refresh(cache_key)

        asyncio.create_task(refresh_task())

    async def _build_tree_response(
        self,
        session: AsyncSession,
        scope: FolderReadScope,
        cache_key: tuple[object, ...],
    ) -> Response:
        if scope.require_existing_client:
            await self._require_client(scope.client_id, session=session)
        tree = await build_tree(
            session,
            scope.client_id,
            visible_since=scope.visible_since(),
            project_path=scope.project_path.value,
        )
        return await store_json_response_async(
            cache_key,
            tree,
            resources={"tree"},
            client_id=scope.client_id,
        )

    async def _build_terminal_projects_response(
        self,
        session: AsyncSession,
        scope: FolderReadScope,
        cache_key: tuple[object, ...],
    ) -> Response:
        if scope.require_existing_client:
            await self._require_client(scope.client_id, session=session)
        projects = await list_terminal_projects(
            session,
            scope.client_id,
            visible_since=scope.visible_since(),
        )
        return await store_json_response_async(
            cache_key,
            projects,
            resources={"tree"},
            client_id=scope.client_id,
        )

    async def _build_activity_response(
        self,
        session: AsyncSession,
        scope: FolderReadScope,
        *,
        include_runtime_tags: bool,
        cache_key: tuple[object, ...],
    ) -> Response:
        await self._require_client(scope.client_id, session=session)
        activity = await load_client_windows_activity(
            session,
            scope.client_id,
            include_runtime_tags=include_runtime_tags,
            visible_since=scope.visible_since(),
            project_path=scope.project_path.value,
        )
        return await store_json_response_async(
            cache_key,
            activity,
            resources={"window", "tree"},
            client_id=scope.client_id,
        )

    async def _require_client(
        self,
        client_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> Client:
        client = await get_client(session or self._session, client_id)
        if client is None:
            raise FolderApiError(404, "client not found")
        return client

    async def _create_folder(self, client_id: UUID, path: str) -> Folder:
        try:
            folder = await self._get_or_create_folder_and_commit(client_id, path)
        except ValueError as exc:
            raise FolderApiError(400, str(exc)) from exc
        except IntegrityError:
            await self._session.rollback()
            try:
                folder = await self._get_or_create_folder_and_commit(client_id, path)
            except IntegrityError as retry_exc:
                await self._session.rollback()
                raise FolderApiError(409, "folder path conflict; retry request") from retry_exc
            except ValueError as retry_exc:
                raise FolderApiError(400, str(retry_exc)) from retry_exc
        return folder

    async def _get_or_create_folder_and_commit(self, client_id: UUID, path: str) -> Folder:
        folder = await get_or_create_folder_by_path(self._session, client_id, path)
        await self._session.commit()
        return folder

    def _tree_cache_key(self, scope: FolderReadScope) -> tuple[object, ...]:
        return (
            "tree",
            response_cache_scope(self._session),
            scope.client_id,
            scope.time_range.cache_token,
            scope.project_path.value,
        )

    def _terminal_projects_cache_key(self, scope: FolderReadScope) -> tuple[object, ...]:
        return (
            "terminal-projects",
            response_cache_scope(self._session),
            scope.client_id,
            scope.time_range.cache_token,
        )

    def _activity_cache_key(
        self,
        scope: FolderReadScope,
        include_runtime_tags: bool,
    ) -> tuple[object, ...]:
        return (
            "activity",
            response_cache_scope(self._session),
            scope.client_id,
            include_runtime_tags,
            scope.time_range.cache_token,
            scope.project_path.value,
        )


def folder_out(folder: Folder) -> FolderOut:
    return FolderOut(id=folder.id, name=folder.name, path=folder.path)
