from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

from app.config import Settings
from app.contexts.workspace.application import project_todo_attachment_staging
from app.contexts.workspace.application.project_todo_attachment_staging import (
    StagedProjectTodoAttachment,
    append_project_todo_attachment_context,
    stage_project_todo_attachments_for_prompt,
)


class FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return False


class FakeObjectStorage:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.read_keys: list[str] = []

    async def read_object(self, object_key: str) -> bytes:
        self.read_keys.append(object_key)
        return self.objects[object_key]


class FakeBroker:
    def __init__(self) -> None:
        self.writes: list[tuple[UUID, str, bytes, bool]] = []

    async def write_file_bytes(self, client_id: UUID, path: str, data: bytes, *, overwrite: bool) -> None:
        self.writes.append((client_id, path, data, overwrite))


def test_append_project_todo_attachment_context_adds_local_paths() -> None:
    prompt = append_project_todo_attachment_context(
        "Base prompt\n",
        [
            StagedProjectTodoAttachment(
                filename="screen.png",
                path="/tmp/web-terminal-acp/project-todo-attachments/todo/attachment/screen.png",
                content_type="image/png",
                size_bytes=123,
            )
        ],
    )

    assert prompt.startswith("Base prompt\n\n# Attached Files")
    assert "1. screen.png (image/png, 123 bytes)" in prompt
    assert "Local file path: /tmp/web-terminal-acp/project-todo-attachments/todo/attachment/screen.png" in prompt
    assert "supports file path input" in prompt


@pytest.mark.asyncio
async def test_stage_project_todo_attachments_writes_uploaded_objects_to_client_path(monkeypatch) -> None:
    client_id = UUID("00000000-0000-0000-0000-000000000001")
    todo_id = UUID("00000000-0000-0000-0000-000000000002")
    uploaded_id = UUID("00000000-0000-0000-0000-000000000003")
    pending_id = UUID("00000000-0000-0000-0000-000000000004")
    uploaded = SimpleNamespace(
        id=uploaded_id,
        project_todo_id=todo_id,
        object_key="objects/uploaded.png",
        filename="screen.png",
        content_type="image/png",
        size_bytes=None,
        status="uploaded",
    )
    pending = SimpleNamespace(
        id=pending_id,
        project_todo_id=todo_id,
        object_key="objects/pending.png",
        filename="draft.png",
        content_type="image/png",
        size_bytes=10,
        status="pending",
    )

    async def fake_list_attachments(_session, todo_ids):
        assert todo_ids == [todo_id]
        return {todo_id: [uploaded, pending]}

    monkeypatch.setattr(
        project_todo_attachment_staging,
        "list_project_todo_attachments_for_todos",
        fake_list_attachments,
    )
    storage = FakeObjectStorage({"objects/uploaded.png": b"image-bytes"})
    broker = FakeBroker()
    settings = Settings(
        _env_file=None,
        project_todo_attachment_max_bytes=1024,
        project_todo_attachment_client_temp_root="/client/tmp/todo-images",
    )

    prompt = await stage_project_todo_attachments_for_prompt(
        client_id=client_id,
        todo_id=todo_id,
        prompt="Todo prompt",
        session_factory=FakeSessionContext,
        broker=broker,
        storage=storage,
        settings=settings,
    )

    target_path = (
        "/client/tmp/todo-images/"
        "00000000-0000-0000-0000-000000000002/"
        "00000000-0000-0000-0000-000000000003/"
        "screen.png"
    )
    assert storage.read_keys == ["objects/uploaded.png"]
    assert broker.writes == [(client_id, target_path, b"image-bytes", True)]
    assert "Todo prompt\n\n# Attached Files" in prompt
    assert f"Local file path: {target_path}" in prompt
    assert "draft.png" not in prompt


@pytest.mark.asyncio
async def test_stage_project_todo_attachments_rejects_oversized_download(monkeypatch) -> None:
    todo_id = UUID("00000000-0000-0000-0000-000000000002")
    attachment = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000003"),
        project_todo_id=todo_id,
        object_key="objects/large.png",
        filename="large.png",
        content_type="image/png",
        size_bytes=2048,
        status="uploaded",
    )

    async def fake_list_attachments(_session, _todo_ids):
        return {todo_id: [attachment]}

    monkeypatch.setattr(
        project_todo_attachment_staging,
        "list_project_todo_attachments_for_todos",
        fake_list_attachments,
    )

    with pytest.raises(ValueError, match="attachment is too large"):
        await stage_project_todo_attachments_for_prompt(
            client_id=UUID("00000000-0000-0000-0000-000000000001"),
            todo_id=todo_id,
            prompt="Todo prompt",
            session_factory=FakeSessionContext,
            broker=FakeBroker(),
            storage=FakeObjectStorage({"objects/large.png": b"large"}),
            settings=Settings(_env_file=None, project_todo_attachment_max_bytes=4),
        )
