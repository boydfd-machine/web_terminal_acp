from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.contexts.workspace.api import project_todos_routes


class _Session:
    bind = None

    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_list_todos_route_passes_completion_verification_scheduler(monkeypatch) -> None:
    client_id = uuid4()
    registry = object()
    session = _Session()
    session_factory = object()
    scheduler = object()
    captured: dict[str, object] = {}

    async def require_client(_session, required_client_id):
        captured["required_client_id"] = required_client_id

    async def dispatch_ready_project_todos(**kwargs):
        captured["dispatch_kwargs"] = kwargs

    async def list_project_todos(_session, list_client_id, list_project_path, **kwargs):
        captured["list_client_id"] = list_client_id
        captured["list_project_path"] = list_project_path
        captured["list_kwargs"] = kwargs
        return []

    async def list_project_todo_artifact_candidates(*_args, **_kwargs):
        return []

    async def create_missing_project_todo_requested_artifacts(*_args, **_kwargs):
        return []

    async def project_todo_list_responses(*_args, **_kwargs):
        return []

    def make_verification_scheduler(**kwargs):
        captured["scheduler_kwargs"] = kwargs
        return scheduler

    def background_session_factory_for(received_session):
        captured["background_session"] = received_session
        return session_factory

    monkeypatch.setattr(project_todos_routes, "require_client", require_client)
    monkeypatch.setattr(project_todos_routes, "client_connection_registry_from_state", lambda _state: registry)
    monkeypatch.setattr(project_todos_routes, "dispatch_ready_project_todos", dispatch_ready_project_todos)
    monkeypatch.setattr(project_todos_routes, "list_project_todos", list_project_todos)
    monkeypatch.setattr(
        project_todos_routes,
        "list_project_todo_artifact_candidates",
        list_project_todo_artifact_candidates,
    )
    monkeypatch.setattr(
        project_todos_routes,
        "create_missing_project_todo_requested_artifacts",
        create_missing_project_todo_requested_artifacts,
    )
    monkeypatch.setattr(project_todos_routes, "pop_project_todo_artifact_generations", lambda _session: [])
    monkeypatch.setattr(project_todos_routes, "project_todo_list_responses", project_todo_list_responses)
    monkeypatch.setattr(project_todos_routes, "make_verification_scheduler", make_verification_scheduler)
    monkeypatch.setattr(project_todos_routes, "background_session_factory_for", background_session_factory_for)
    monkeypatch.setattr(project_todos_routes, "ui_event_hub_from_state", lambda _state: object())

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    result = await project_todos_routes.list_todos(
        client_id=client_id,
        project_path="/workspace/project",
        request=request,
        updated_range=None,
        start_date=None,
        end_date=None,
        session=session,
        tmux_manager=object(),
    )

    assert result.todos == []
    assert session.commits == 1
    assert captured["required_client_id"] == client_id
    assert captured["background_session"] is session
    assert captured["scheduler_kwargs"] == {
        "client_id": client_id,
        "session_factory": session_factory,
        "registry": registry,
    }
    assert captured["list_client_id"] == client_id
    assert captured["list_project_path"] == "/workspace/project"
    list_kwargs = captured["list_kwargs"]
    assert list_kwargs["verification_scheduler"] is scheduler
    assert callable(list_kwargs["remote_client_available"])
