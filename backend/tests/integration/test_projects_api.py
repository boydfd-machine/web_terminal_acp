from __future__ import annotations

import base64

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.contexts.workspace.application.project_file_search import MAX_SEARCH_FILE_BYTES
from app.db import Base, get_session
from app.main import app
from app.models import GitWorktreeRun, LOCAL_CLIENT_ID, WindowGitBinding
from app.repositories.clients import ensure_local_client
from app.contexts.windows.infrastructure.repository import create_window
from app.routers.projects import PROJECT_FILE_PREVIEW_BYTES


class DbClient:
    def __init__(self, client: AsyncClient, session_factory: async_sessionmaker):
        self._client = client
        self.session_factory = session_factory

    async def get(self, *args, **kwargs):
        return await self._client.get(*args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self._client.post(*args, **kwargs)

    async def put(self, *args, **kwargs):
        return await self._client.put(*args, **kwargs)


@pytest.fixture
async def db_client(tmp_path):
    for state_name in ("client_connections", "terminal_broker", "local_terminal_runtime"):
        if hasattr(app.state, state_name):
            delattr(app.state, state_name)
    database_path = tmp_path / "projects.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        await ensure_local_client(session)
        await session.commit()

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield DbClient(test_client, session_factory)
    finally:
        app.dependency_overrides.pop(get_session, None)
        for state_name in ("client_connections", "terminal_broker", "local_terminal_runtime"):
            if hasattr(app.state, state_name):
                delattr(app.state, state_name)
        await engine.dispose()


@pytest.mark.asyncio
async def test_project_detail_lists_project_domain_objects(db_client, tmp_path) -> None:
    project_dir = tmp_path / "project-a"
    project_dir.mkdir()
    async with db_client.session_factory() as session:
        await create_window(session, LOCAL_CLIENT_ID, str(project_dir), "/bin/bash")
        await session.commit()

    response = await db_client.get(f"/api/clients/{LOCAL_CLIENT_ID}/projects")

    assert response.status_code == 200
    assert response.json()[0]["path"] == str(project_dir)
    assert response.json()[0]["window_count"] == 1


@pytest.mark.asyncio
async def test_project_detail_reads_and_updates_agent_preference(db_client, tmp_path) -> None:
    project_dir = tmp_path / "project-agent-preference"
    project_dir.mkdir()
    async with db_client.session_factory() as session:
        await create_window(session, LOCAL_CLIENT_ID, str(project_dir), "/bin/bash")
        await session.commit()

    detail_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/detail",
        params={"project_path": str(project_dir)},
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["agent_preference"] == {
        "agent_profile_id": None,
        "agent_client": None,
        "agent_command": None,
        "agent_model_selection": None,
    }

    update_response = await db_client.put(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/agent-preference",
        params={"project_path": str(project_dir)},
        json={
            "agent_profile_id": "builtin/developer",
            "agent_client": "codex",
            "agent_command": "codex --dangerously-bypass-approvals-and-sandbox",
            "agent_model_selection": {
                "preset_id": "openai-main",
                "model": "gpt-5-codex",
            },
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "agent_profile_id": "builtin/developer",
        "agent_client": "codex",
        "agent_command": "codex --dangerously-bypass-approvals-and-sandbox",
        "agent_model_selection": {
            "preset_id": "openai-main",
            "model": "gpt-5-codex",
        },
    }

    refreshed_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/detail",
        params={"project_path": str(project_dir)},
    )

    assert refreshed_response.status_code == 200
    assert refreshed_response.json()["agent_preference"] == update_response.json()


@pytest.mark.asyncio
async def test_project_files_list_preview_upload_and_download(db_client, tmp_path) -> None:
    project_dir = tmp_path / "project-b"
    nested_dir = project_dir / "docs"
    nested_dir.mkdir(parents=True)
    readme = nested_dir / "README.md"
    readme.write_text("# Demo\n\nhello", encoding="utf-8")
    async with db_client.session_factory() as session:
        await create_window(session, LOCAL_CLIENT_ID, str(project_dir), "/bin/bash")
        await session.commit()

    list_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files",
        params={"project_path": str(project_dir), "path": "."},
    )
    assert list_response.status_code == 200
    assert list_response.json()["entries"][0]["path"] == "docs"
    assert list_response.json()["entries"][0]["kind"] == "directory"

    preview_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files/content",
        params={"project_path": str(project_dir), "path": "docs/README.md"},
    )
    assert preview_response.status_code == 200
    assert preview_response.json()["content"] == "# Demo\n\nhello"

    extensionless = nested_dir / "Makefile"
    extensionless.write_text("all:\n\techo hello", encoding="utf-8")
    extensionless_preview_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files/content",
        params={"project_path": str(project_dir), "path": "docs/Makefile"},
    )
    assert extensionless_preview_response.status_code == 200
    assert extensionless_preview_response.json()["content"] == "all:\n\techo hello"

    save_response = await db_client.put(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files/content",
        params={"project_path": str(project_dir)},
        json={
            "path": "docs/README.md",
            "content": "# Demo\n\nupdated",
            "overwrite": True,
        },
    )
    assert save_response.status_code == 200
    assert readme.read_text(encoding="utf-8") == "# Demo\n\nupdated"

    upload_response = await db_client.post(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files/upload",
        params={"project_path": str(project_dir)},
        json={
            "path": "docs/upload.txt",
            "content_base64": base64.b64encode(b"uploaded").decode("ascii"),
            "overwrite": True,
        },
    )
    assert upload_response.status_code == 200
    assert (nested_dir / "upload.txt").read_text(encoding="utf-8") == "uploaded"

    download_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files/download",
        params={"project_path": str(project_dir), "path": "docs/upload.txt"},
    )
    assert download_response.status_code == 200
    assert download_response.content == b"uploaded"


@pytest.mark.asyncio
async def test_project_file_preview_rejects_binary_files(db_client, tmp_path) -> None:
    project_dir = tmp_path / "project-binary"
    project_dir.mkdir()
    binary_file = project_dir / "image.bin"
    binary_file.write_bytes(b"\x00\x01\x02\x03")
    async with db_client.session_factory() as session:
        await create_window(session, LOCAL_CLIENT_ID, str(project_dir), "/bin/bash")
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files/content",
        params={"project_path": str(project_dir), "path": "image.bin"},
    )

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_project_file_preview_reports_truncation(db_client, tmp_path) -> None:
    project_dir = tmp_path / "project-large"
    project_dir.mkdir()
    large_file = project_dir / "large.txt"
    large_file.write_text("a" * (PROJECT_FILE_PREVIEW_BYTES + 1), encoding="utf-8")
    async with db_client.session_factory() as session:
        await create_window(session, LOCAL_CLIENT_ID, str(project_dir), "/bin/bash")
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files/content",
        params={"project_path": str(project_dir), "path": "large.txt"},
    )

    assert response.status_code == 200
    assert response.json()["truncated"] is True
    assert len(response.json()["content"]) == PROJECT_FILE_PREVIEW_BYTES


@pytest.mark.asyncio
async def test_project_files_reject_path_escape(db_client, tmp_path) -> None:
    project_dir = tmp_path / "project-c"
    project_dir.mkdir()
    async with db_client.session_factory() as session:
        await create_window(session, LOCAL_CLIENT_ID, str(project_dir), "/bin/bash")
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files/content",
        params={"project_path": str(project_dir), "path": "../secret.txt"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_project_files_support_registered_worktree_browse_root(db_client, tmp_path) -> None:
    project_dir = tmp_path / "project-main"
    project_dir.mkdir()
    worktree_dir = tmp_path / "project-feature"
    worktree_dir.mkdir()
    (worktree_dir / "feature.txt").write_text("worktree file", encoding="utf-8")
    async with db_client.session_factory() as session:
        window = await create_window(session, LOCAL_CLIENT_ID, str(worktree_dir), "/bin/bash")
        session.add(
            WindowGitBinding(
                client_id=LOCAL_CLIENT_ID,
                virtual_window_id=window.id,
                main_repo_root=str(project_dir),
                worktree_root=str(worktree_dir),
                branch="feature/files",
                discovery_method="marker",
            )
        )
        session.add(
            GitWorktreeRun(
                client_id=LOCAL_CLIENT_ID,
                virtual_window_id=window.id,
                command_sequence="1",
                status="completed",
                pending_commit=True,
            )
        )
        await session.commit()

    roots_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/browse-roots",
        params={"project_path": str(project_dir)},
    )
    assert roots_response.status_code == 200
    assert roots_response.json()["roots"] == [
        {
            "kind": "main",
            "project_path": str(project_dir),
            "browse_root": None,
            "branch": None,
            "pending_commit": False,
        },
        {
            "kind": "worktree",
            "project_path": str(project_dir),
            "browse_root": str(worktree_dir),
            "branch": "feature/files",
            "pending_commit": True,
        },
    ]
    worktree_roots_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/browse-roots",
        params={"project_path": str(worktree_dir)},
    )
    assert worktree_roots_response.status_code == 200
    assert worktree_roots_response.json()["roots"][0]["project_path"] == str(project_dir)

    files_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files",
        params={
            "project_path": str(project_dir),
            "browse_root": str(worktree_dir),
            "path": ".",
        },
    )
    assert files_response.status_code == 200
    assert files_response.json()["project_path"] == str(project_dir)
    assert files_response.json()["entries"][0]["path"] == "feature.txt"

    worktree_project_files_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files",
        params={"project_path": str(worktree_dir), "path": "."},
    )
    assert worktree_project_files_response.status_code == 200
    assert worktree_project_files_response.json()["project_path"] == str(project_dir)
    assert worktree_project_files_response.json()["entries"][0]["path"] == "feature.txt"

    rejected_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files",
        params={
            "project_path": str(project_dir),
            "browse_root": str(tmp_path / "unregistered"),
            "path": ".",
        },
    )
    assert rejected_response.status_code == 400


@pytest.mark.asyncio
async def test_project_file_search_defaults_to_main_root_and_skips_worktrees(db_client, tmp_path) -> None:
    project_dir = tmp_path / "project-main"
    source_dir = project_dir / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text("first\nneedle main hit\nthird\n", encoding="utf-8")
    large_filename_match = source_dir / "zz-needle-large.bin"
    large_filename_match.write_bytes(b"x" * (MAX_SEARCH_FILE_BYTES + 1))
    node_modules_dir = project_dir / "node_modules" / "slow-package"
    node_modules_dir.mkdir(parents=True)
    (node_modules_dir / "index.js").write_text("needle package hit\n", encoding="utf-8")
    worktree_dir = project_dir / ".web-terminal-acp" / "worktrees" / "feature"
    worktree_source_dir = worktree_dir / "src"
    worktree_source_dir.mkdir(parents=True)
    (worktree_source_dir / "feature.py").write_text("needle worktree hit\n", encoding="utf-8")
    unregistered_worktree_dir = project_dir / "feature-copy"
    unregistered_worktree_source_dir = unregistered_worktree_dir / "src"
    unregistered_worktree_source_dir.mkdir(parents=True)
    (unregistered_worktree_dir / ".git").write_text("gitdir: ../.git/worktrees/feature-copy\n", encoding="utf-8")
    (unregistered_worktree_source_dir / "copy.py").write_text("needle unregistered worktree hit\n", encoding="utf-8")

    async with db_client.session_factory() as session:
        window = await create_window(session, LOCAL_CLIENT_ID, str(worktree_dir), "/bin/bash")
        await create_window(session, LOCAL_CLIENT_ID, str(unregistered_worktree_dir), "/bin/bash")
        session.add(
            WindowGitBinding(
                client_id=LOCAL_CLIENT_ID,
                virtual_window_id=window.id,
                main_repo_root=str(project_dir),
                worktree_root=str(worktree_dir),
                branch="feature/search",
                discovery_method="marker",
            )
        )
        await session.commit()

    response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files/search",
        params={"q": "needle"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "query": "needle",
        "results": [
            {
                "project_path": str(project_dir),
                "path": "src/main.py",
                "line": 2,
                "snippet": "needle main hit",
                "matches": [{"field": "snippet", "start": 0, "end": 6}],
            },
            {
                "project_path": str(project_dir),
                "path": "src/zz-needle-large.bin",
                "line": None,
                "snippet": "src/zz-needle-large.bin",
                "matches": [{"field": "path", "start": 7, "end": 13}],
            }
        ],
        "total": 2,
        "limit": 25,
        "offset": 0,
        "has_more": False,
        "scanned_files": 2,
        "truncated": False,
    }

    content_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files/search",
        params={"q": "needle", "mode": "content"},
    )

    assert content_response.status_code == 200
    assert content_response.json()["results"] == [
        {
            "project_path": str(project_dir),
            "path": "src/main.py",
            "line": 2,
            "snippet": "needle main hit",
            "matches": [{"field": "snippet", "start": 0, "end": 6}],
        }
    ]

    filename_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files/search",
        params={"q": "needle", "mode": "filename"},
    )

    assert filename_response.status_code == 200
    assert filename_response.json()["results"] == [
        {
            "project_path": str(project_dir),
            "path": "src/zz-needle-large.bin",
            "line": None,
            "snippet": "src/zz-needle-large.bin",
            "matches": [{"field": "path", "start": 7, "end": 13}],
        }
    ]

    explicit_worktree_response = await db_client.get(
        f"/api/clients/{LOCAL_CLIENT_ID}/projects/files/search",
        params={"q": "needle", "project_path": str(unregistered_worktree_dir)},
    )

    assert explicit_worktree_response.status_code == 200
    assert explicit_worktree_response.json()["results"] == [
        {
            "project_path": str(unregistered_worktree_dir),
            "path": "src/copy.py",
            "line": 1,
            "snippet": "needle unregistered worktree hit",
            "matches": [{"field": "snippet", "start": 0, "end": 6}],
        }
    ]
