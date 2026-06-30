from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models import LOCAL_CLIENT_ID, ClientRuntime, VirtualWindow, WindowStatus
from app.routers import windows
from app.schemas import WindowCloneIn, WindowCreateIn
from app.services import agent_config as agent_config_service
from app.contexts.windows.api import window_detail_routes
from app.contexts.windows.application import window_cloning as window_cloning_service
from app.contexts.windows.application import window_creation as window_creation_service


class FakeSession:
    async def commit(self) -> None:
        return None

    async def refresh(self, _instance) -> None:
        return None

    async def rollback(self) -> None:
        return None


@pytest.fixture(autouse=True)
def skip_agent_config_file_restore(monkeypatch, tmp_path):
    async def fake_restore_system(_session, *, home=None) -> None:
        return None

    async def fake_restore_profiles(_session, *, owner_user_id=None, home=None):
        return home or tmp_path

    monkeypatch.setattr(
        window_creation_service.system_config_service,
        "restore_system_agent_config_files_to_disk",
        fake_restore_system,
    )
    monkeypatch.setattr(
        window_creation_service.agent_profile_service,
        "restore_agent_profile_files_to_disk",
        fake_restore_profiles,
    )


@pytest.mark.asyncio
async def test_local_window_creation_persists_before_scheduling_tmux_start(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    folder_id = uuid4()

    def fake_schedule(**kwargs):
        events.append(("tmux", kwargs["window_id"]))

    async def fake_create_window(
        session,
        client_id,
        cwd,
        shell_command,
        *,
        window_id=None,
        tmux_session=None,
        tmux_window_id=None,
        remote_session_id=None,
        remote_window_id=None,
        derived_context=None,
    ):
        persisted_window_id = window_id or uuid4()
        events.append(("db", window_id))
        return VirtualWindow(
            id=persisted_window_id,
            client_id=client_id,
            title="Terminal",
            folder_id=folder_id,
            status=WindowStatus.active,
            tmux_session=tmux_session,
            tmux_window_id=tmux_window_id,
            remote_session_id=remote_session_id,
            remote_window_id=remote_window_id,
            cwd=cwd,
            shell_command=shell_command,
            title_manually_overridden=False,
            folder_manually_overridden=False,
            created_at=datetime.now(UTC),
        )

    monkeypatch.setattr(window_creation_service, "create_window", fake_create_window)
    monkeypatch.setattr(window_creation_service, "schedule_local_window_runtime_start", fake_schedule)
    client = SimpleNamespace(id=LOCAL_CLIENT_ID, runtime=ClientRuntime.local)

    result = await window_creation_service.create_virtual_window_for_client(
        client,
        WindowCreateIn(cwd="/workspace", shell_command="/bin/bash"),
        FakeSession(),
        object(),
        session_factory=FakeSession,
    )
    created = result.window

    assert events[0][0] == "db"
    assert events[1] == ("tmux", events[0][1])
    assert created.tmux_session is None
    assert created.tmux_window_id is None


@pytest.mark.asyncio
async def test_local_agent_window_applies_config_before_tmux_create(monkeypatch) -> None:
    events: list[tuple[str, object]] = []

    def fake_schedule(**kwargs):
        events.append(("tmux", kwargs["shell_command"]))

    async def fake_create_window(session, client_id, cwd, shell_command, **kwargs):
        window_id = kwargs["window_id"]
        events.append(("db", shell_command))
        return VirtualWindow(
            id=window_id,
            client_id=client_id,
            title="Terminal",
            folder_id=None,
            status=WindowStatus.active,
            tmux_session=kwargs.get("tmux_session"),
            tmux_window_id=kwargs.get("tmux_window_id"),
            remote_session_id=None,
            remote_window_id=None,
            cwd=cwd,
            shell_command=shell_command,
            title_manually_overridden=False,
            folder_manually_overridden=False,
            created_at=datetime.now(UTC),
        )

    def fake_apply(selection, *, window_id, home=None, protect_system_config_skills=False):
        events.append(("config", (selection.agent, window_id)))
        return agent_config_service.AgentConfig(agent="codex", sections=[])

    monkeypatch.setattr(window_creation_service, "create_window", fake_create_window)
    monkeypatch.setattr(window_creation_service.agent_config_service, "apply_agent_config_selection", fake_apply)
    monkeypatch.setattr(window_creation_service, "schedule_local_window_runtime_start", fake_schedule)

    client = SimpleNamespace(id=LOCAL_CLIENT_ID, runtime=ClientRuntime.local)
    result = await window_creation_service.create_virtual_window_for_client(
        client,
        WindowCreateIn.model_validate(
            {
                "cwd": "/workspace",
                "agent_launch": {
                    "agent": "codex",
                    "command": "codex",
                    "config": {"agent": "codex", "sections": [{"id": "skills", "items": [{"id": "docker", "enabled": False}]}]},
                },
            }
        ),
        FakeSession(),
        object(),
        session_factory=FakeSession,
    )
    created = result.window

    assert [event[0] for event in events] == ["config", "db", "tmux"]
    assert created.shell_command == "codex"
    assert "codex" in result.runtime_tags


@pytest.mark.asyncio
async def test_local_agent_window_materializes_profile_before_tmux_create(monkeypatch) -> None:
    events: list[tuple[str, object]] = []

    def fake_schedule(**kwargs):
        events.append(("tmux", kwargs["shell_command"]))

    async def fake_create_window(session, client_id, cwd, shell_command, **kwargs):
        window_id = kwargs["window_id"]
        events.append(("db", shell_command))
        return VirtualWindow(
            id=window_id,
            client_id=client_id,
            title="Terminal",
            folder_id=None,
            status=WindowStatus.active,
            tmux_session=kwargs.get("tmux_session"),
            tmux_window_id=kwargs.get("tmux_window_id"),
            remote_session_id=None,
            remote_window_id=None,
            cwd=cwd,
            shell_command=shell_command,
            title_manually_overridden=False,
            folder_manually_overridden=False,
            created_at=datetime.now(UTC),
        )

    def fake_materialize(profile_id, agent, *, window_id, home=None):
        events.append(("profile", (profile_id, agent, window_id)))
        return agent_config_service.AgentConfig(agent="codex", sections=[])

    monkeypatch.setattr(window_creation_service, "create_window", fake_create_window)
    monkeypatch.setattr(
        window_creation_service.agent_profile_service,
        "materialize_agent_profile_for_window",
        fake_materialize,
    )
    monkeypatch.setattr(window_creation_service, "schedule_local_window_runtime_start", fake_schedule)

    client = SimpleNamespace(id=LOCAL_CLIENT_ID, runtime=ClientRuntime.local)
    result = await window_creation_service.create_virtual_window_for_client(
        client,
        WindowCreateIn.model_validate(
            {
                "cwd": "/workspace",
                "agent_launch": {
                    "agent": "codex",
                    "command": "codex",
                    "profile_id": "builder",
                },
            }
        ),
        FakeSession(),
        object(),
        session_factory=FakeSession,
    )
    created = result.window

    assert [event[0] for event in events] == ["profile", "db", "tmux"]
    assert events[0][1] == ("builder", "codex", str(created.id))


@pytest.mark.asyncio
async def test_local_window_clone_copies_agent_home_before_tmux_create(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    source_id = uuid4()
    folder_id = uuid4()
    source_window = VirtualWindow(
        id=source_id,
        client_id=LOCAL_CLIENT_ID,
        title="Agent",
        folder_id=folder_id,
        status=WindowStatus.active,
        cwd="/workspace",
        shell_command="codex",
        title_manually_overridden=True,
        folder_manually_overridden=True,
        created_at=datetime.now(UTC),
    )

    def fake_schedule(**kwargs):
        events.append(("tmux", kwargs["window_id"], kwargs["shell_command"]))

    async def fake_create_window(session, client_id, cwd, shell_command, **kwargs):
        events.append(("db", kwargs["window_id"]))
        return VirtualWindow(
            id=kwargs["window_id"],
            client_id=client_id,
            title=kwargs["title"],
            folder_id=kwargs["folder_id"],
            status=WindowStatus.active,
            tmux_session=kwargs.get("tmux_session"),
            tmux_window_id=kwargs.get("tmux_window_id"),
            remote_session_id=None,
            remote_window_id=None,
            cwd=cwd,
            shell_command=shell_command,
            title_manually_overridden=kwargs["title_manually_overridden"],
            folder_manually_overridden=kwargs["folder_manually_overridden"],
            parent_window_id=kwargs["parent_window_id"],
            root_window_id=kwargs["root_window_id"],
            derived_mode=kwargs["derived_mode"],
            derived_context=kwargs["derived_context"],
            created_at=datetime.now(UTC),
        )

    def fake_clone(source_window_id, target_window_id, *, source_cwd=None):
        events.append(("clone", (source_window_id, target_window_id, source_cwd)))
        return SimpleNamespace(
            cloned_agents=("codex",),
            session_ids={"codex": "new-session"},
            resume_commands={"codex": "codex resume new-session"},
        )

    monkeypatch.setattr(window_cloning_service, "create_window", fake_create_window)
    monkeypatch.setattr(window_cloning_service, "clone_window_agent_homes", fake_clone)
    monkeypatch.setattr(window_cloning_service, "schedule_local_window_runtime_start", fake_schedule)

    client = SimpleNamespace(id=LOCAL_CLIENT_ID, runtime=ClientRuntime.local)
    result = await window_cloning_service.clone_virtual_window_for_client(
        client,
        source_window,
        WindowCloneIn(),
        FakeSession(),
        object(),
        session_factory=FakeSession,
    )
    created = result.window

    assert [event[0] for event in events] == ["clone", "db", "tmux"]
    assert events[0][1][0] == source_id
    assert events[0][1][1] == events[1][1]
    assert events[0][1][2] == "/workspace"
    assert events[2][2] == "codex resume new-session"
    assert created.parent_window_id == source_id
    assert created.root_window_id == source_id
    assert created.derived_mode == "linked"
    assert created.folder_id == folder_id
    assert created.derived_context["resume_commands"] == {"codex": "codex resume new-session"}


def test_remote_agent_from_command_uses_remote_descriptor_after_shell_prefix() -> None:
    payload = {
        "agent_clients": [
            {
                "id": "future_agent",
                "provider_id": "future_provider",
                "aliases": ["future"],
                "default_command": "future-agent",
                "command_names": ["future-agent"],
            }
        ]
    }

    assert windows._remote_agent_from_command(
        "cd /workspace && FOO=bar future-agent --profile main",
        payload,
    ) == "future_agent"


@pytest.mark.asyncio
async def test_local_window_agent_config_reads_managed_window_home(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    client_id = LOCAL_CLIENT_ID
    window_id = uuid4()
    window = VirtualWindow(
        id=window_id,
        client_id=client_id,
        title="Agent",
        folder_id=None,
        status=WindowStatus.active,
        cwd="/workspace",
        shell_command="codex",
        title_manually_overridden=False,
        folder_manually_overridden=False,
        created_at=datetime.now(UTC),
    )

    async def fake_require_client(session, requested_client_id):
        assert requested_client_id == client_id
        return SimpleNamespace(id=client_id, runtime=ClientRuntime.local)

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        assert requested_client_id == client_id
        assert requested_window_id == window_id
        return window

    async def fake_agent_provider_for_window(session, requested_window):
        assert requested_window is window
        return "codex"

    def fake_list_window_agent_config(agent, *, window_id, home=None):
        events.append(("window_config", (agent, window_id)))
        return agent_config_service.AgentConfig(
            agent="codex",
            sections=[
                agent_config_service.AgentConfigSection(
                    id="skills",
                    name="Skills",
                    items=[
                        agent_config_service.AgentConfigItem(
                            id="docker",
                            name="docker",
                            enabled=False,
                        )
                    ],
                )
            ],
        )

    def fail_list_agent_config(*args, **kwargs):
        raise AssertionError("window config must not read the global agent home")

    monkeypatch.setattr(window_detail_routes, "_require_client", fake_require_client)
    monkeypatch.setattr(window_detail_routes, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(window_detail_routes, "_agent_provider_for_window", fake_agent_provider_for_window)
    monkeypatch.setattr(
        windows.agent_config_service,
        "list_window_agent_config",
        fake_list_window_agent_config,
        raising=False,
    )
    monkeypatch.setattr(windows.agent_config_service, "list_agent_config", fail_list_agent_config)
    monkeypatch.setattr(
        window_detail_routes.system_config_service,
        "list_system_model_presets",
        AsyncMock(return_value=agent_config_service.SystemModelPresetList(presets=[])),
    )

    result = await window_detail_routes.read_window_agent_config(
        SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace())),
        client_id,
        window_id,
        FakeSession(),
    )

    assert events == [("window_config", ("codex", str(window_id)))]
    assert result.sections[0].items[0].enabled is False


@pytest.mark.asyncio
async def test_local_window_agent_config_update_writes_managed_window_home(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    client_id = LOCAL_CLIENT_ID
    window_id = uuid4()
    window = VirtualWindow(
        id=window_id,
        client_id=client_id,
        title="Agent",
        folder_id=None,
        status=WindowStatus.active,
        cwd="/workspace",
        shell_command="codex",
        title_manually_overridden=False,
        folder_manually_overridden=False,
        created_at=datetime.now(UTC),
    )

    async def fake_require_client(session, requested_client_id):
        assert requested_client_id == client_id
        return SimpleNamespace(id=client_id, runtime=ClientRuntime.local)

    async def fake_get_window_for_client(session, requested_client_id, requested_window_id):
        assert requested_client_id == client_id
        assert requested_window_id == window_id
        return window

    async def fake_agent_provider_for_window(session, requested_window):
        assert requested_window is window
        return "codex"

    def fake_set_window_agent_config_item_enabled(agent, section_id, item_id, enabled, *, window_id, home=None):
        events.append(("window_config", (agent, section_id, item_id, enabled, window_id)))
        return agent_config_service.AgentConfig(
            agent="codex",
            sections=[
                agent_config_service.AgentConfigSection(
                    id="skills",
                    name="Skills",
                    items=[
                        agent_config_service.AgentConfigItem(
                            id=item_id,
                            name=item_id,
                            enabled=enabled,
                        )
                    ],
                )
            ],
        )

    def fail_set_agent_config_item_enabled(*args, **kwargs):
        raise AssertionError("window config must not write the global agent home")

    monkeypatch.setattr(window_detail_routes, "_require_client", fake_require_client)
    monkeypatch.setattr(window_detail_routes, "get_window_for_client", fake_get_window_for_client)
    monkeypatch.setattr(window_detail_routes, "_agent_provider_for_window", fake_agent_provider_for_window)
    monkeypatch.setattr(
        windows.agent_config_service,
        "set_window_agent_config_item_enabled",
        fake_set_window_agent_config_item_enabled,
        raising=False,
    )
    monkeypatch.setattr(
        windows.agent_config_service,
        "set_agent_config_item_enabled",
        fail_set_agent_config_item_enabled,
    )

    result = await window_detail_routes.update_window_agent_config_item(
        SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace())),
        client_id,
        window_id,
        "skills",
        "docker",
        window_detail_routes.AgentConfigToggleIn(enabled=False),
        FakeSession(),
    )

    assert events == [("window_config", ("codex", "skills", "docker", False, str(window_id)))]
    assert result.sections[0].items[0].enabled is False
