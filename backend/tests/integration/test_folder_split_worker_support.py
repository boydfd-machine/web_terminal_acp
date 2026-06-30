from __future__ import annotations

from dataclasses import dataclass

from datetime import datetime, timezone

from uuid import uuid4

import pytest

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.model_base import Base

from app.models import Event, EventSourceType, Folder, FolderSplitJob, FolderSplitJobStatus, VirtualWindow

from app.repositories.clients import create_client, ensure_local_client

from app.repositories.folder_split_jobs import enqueue_folder_split_job

from app.domain.folders import MAX_FOLDER_PATH_LENGTH
from app.repositories.folders import get_or_create_folder_by_path

from app.contexts.windows.infrastructure.repository import create_window

from app.services import folder_split_worker as folder_split_worker_module

from app.services.folder_split_worker import process_folder_split_jobs_once, process_next_folder_split_job

from app.services.folder_splitter import FolderSplitChild, FolderSplitResult

from app.services.search_index import SUMMARIES_INDEX

@dataclass
class FakeFolderSplitter:
    seen_parent_path: str | None = None
    seen_parent_name: str | None = None
    seen_summary_output_language: str | None = None
    seen_terminals: list[dict] | None = None

    async def split(
        self,
        parent_path: str,
        parent_name: str,
        summary_output_language: str,
        terminals: list[dict],
    ) -> FolderSplitResult:
        self.seen_parent_path = parent_path
        self.seen_parent_name = parent_name
        self.seen_summary_output_language = summary_output_language
        self.seen_terminals = terminals
        return FolderSplitResult(
            children=[
                FolderSplitChild(
                    name="前端展示",
                    terminal_ids=[terminal["id"] for terminal in terminals[:3]],
                ),
                FolderSplitChild(
                    name="后端摘要",
                    terminal_ids=[terminal["id"] for terminal in terminals[3:]],
                ),
            ]
        )

class FailingFolderSplitter:
    async def split(
        self,
        parent_path: str,
        parent_name: str,
        summary_output_language: str,
        terminals: list[dict],
    ) -> FolderSplitResult:
        raise ValueError("split failed")

class MissingTerminalFolderSplitter:
    async def split(
        self,
        parent_path: str,
        parent_name: str,
        summary_output_language: str,
        terminals: list[dict],
    ) -> FolderSplitResult:
        return FolderSplitResult(
            children=[
                FolderSplitChild(name="前端展示", terminal_ids=[terminal["id"] for terminal in terminals[:3]]),
                FolderSplitChild(name="后端摘要", terminal_ids=[terminal["id"] for terminal in terminals[3:5]]),
            ]
        )

class UnknownTerminalFolderSplitter:
    async def split(
        self,
        parent_path: str,
        parent_name: str,
        summary_output_language: str,
        terminals: list[dict],
    ) -> FolderSplitResult:
        return FolderSplitResult(
            children=[
                FolderSplitChild(name="前端展示", terminal_ids=[terminal["id"] for terminal in terminals[:3]]),
                FolderSplitChild(
                    name="后端摘要",
                    terminal_ids=[*([terminal["id"] for terminal in terminals[3:]]), uuid4()],
                ),
            ]
        )

class ExistingNonLeafChildFolderSplitter:
    async def split(
        self,
        parent_path: str,
        parent_name: str,
        summary_output_language: str,
        terminals: list[dict],
    ) -> FolderSplitResult:
        return FolderSplitResult(
            children=[
                FolderSplitChild(name="已有", terminal_ids=[terminal["id"] for terminal in terminals[:3]]),
                FolderSplitChild(name="新建", terminal_ids=[terminal["id"] for terminal in terminals[3:]]),
            ]
        )

class NearMaxPathFolderSplitter:
    async def split(
        self,
        parent_path: str,
        parent_name: str,
        summary_output_language: str,
        terminals: list[dict],
    ) -> FolderSplitResult:
        return FolderSplitResult(
            children=[
                FolderSplitChild(name="x", terminal_ids=[terminal["id"] for terminal in terminals[:3]]),
                FolderSplitChild(name="yy", terminal_ids=[terminal["id"] for terminal in terminals[3:]]),
            ]
        )

@dataclass
class RecordingFolderSplitter:
    called: bool = False

    async def split(
        self,
        parent_path: str,
        parent_name: str,
        summary_output_language: str,
        terminals: list[dict],
    ) -> FolderSplitResult:
        self.called = True
        return FolderSplitResult(children=[])

@dataclass
class MutatingFolderSplitter:
    session: AsyncSession
    target_folder_id: object | None = None
    target_window_id: object | None = None

    async def split(
        self,
        parent_path: str,
        parent_name: str,
        summary_output_language: str,
        terminals: list[dict],
    ) -> FolderSplitResult:
        first_terminal_id = terminals[0]["id"]
        self.target_window_id = first_terminal_id
        first_window = await self.session.get(VirtualWindow, first_terminal_id)
        assert first_window is not None
        external_folder = await get_or_create_folder_by_path(
            self.session,
            first_window.client_id,
            "/外部移动",
        )
        first_window.folder_id = external_folder.id
        await self.session.flush()
        self.target_folder_id = external_folder.id
        return FolderSplitResult(
            children=[
                FolderSplitChild(
                    name="前端展示",
                    terminal_ids=[terminal["id"] for terminal in terminals[:3]],
                ),
                FolderSplitChild(
                    name="后端摘要",
                    terminal_ids=[terminal["id"] for terminal in terminals[3:]],
                ),
            ]
        )

class FakeElasticsearch:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.indexed_documents = []
        self.closed = False

    async def index(self, **kwargs):
        if self.fail:
            raise RuntimeError("Elasticsearch unavailable")
        self.indexed_documents.append(kwargs)
        return {"result": "created"}

    async def close(self):
        self.closed = True

@pytest.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield Session
    finally:
        await engine.dispose()

def near_max_child_path_parent() -> str:
    segment_lengths = [255, 255, 255, MAX_FOLDER_PATH_LENGTH - 6 - (255 * 3)]
    path = "/" + "/".join("a" * length for length in segment_lengths)
    assert len(path) == MAX_FOLDER_PATH_LENGTH - 2
    return path

async def create_windows_in_folder(
    session: AsyncSession,
    path: str,
    count: int,
    client_id=None,
) -> list[VirtualWindow]:
    if client_id is None:
        client = await ensure_local_client(session)
        client_id = client.id
    folder = await get_or_create_folder_by_path(session, client_id, path)
    windows = []
    for index in range(count):
        window = await create_window(
            session,
            client_id,
            cwd=f"/workspace/project-{index}",
            shell_command="/bin/bash",
        )
        window.folder_id = folder.id
        window.title = f"Terminal {index}"
        window.summary = f"Summary {index}"
        window.title_tags = ["tag", f"tag-{index}"]
        windows.append(window)
    await session.flush()
    return windows

__all__ = [name for name in globals() if not name.startswith("__")]
