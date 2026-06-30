from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.contexts.agent_profiles.application import config_selection as agent_config_service
from app.contexts.windows.api.schemas import WindowCreateIn
from app.contexts.windows.application import window_creation as window_creation_service
from app.models import LOCAL_CLIENT_ID, ClientRuntime, VirtualWindow, WindowStatus


class FakeSession:
    async def commit(self) -> None:
        return None

    async def refresh(self, _instance) -> None:
        return None

    async def rollback(self) -> None:
        return None


@pytest.mark.asyncio
async def test_local_agent_window_applies_launch_config_after_profile_materialization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    events: list[tuple[str, object]] = []

    async def fake_restore_system(_session, *, home=None) -> None:
        return None

    async def fake_restore_profiles(_session, *, owner_user_id=None, home=None):
        return home or tmp_path

    def fake_materialize_builtin(profile_id, agent, *, window_id, home=None):
        events.append(("builtin-profile", (profile_id, agent, window_id)))
        return None

    def fake_materialize_profile(profile_id, agent, *, window_id, home=None):
        events.append(("profile", (profile_id, agent, window_id)))
        return agent_config_service.AgentConfig(agent="codex", sections=[])

    def fake_apply(selection, *, window_id, home=None, protect_system_config_skills=False):
        events.append(("config", (selection.agent, window_id, protect_system_config_skills)))
        return agent_config_service.AgentConfig(agent="codex", sections=[])

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

    def fake_schedule(**kwargs):
        events.append(("tmux", kwargs["shell_command"]))

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
    monkeypatch.setattr(
        window_creation_service.agent_profile_service,
        "materialize_builtin_profile_for_window",
        fake_materialize_builtin,
    )
    monkeypatch.setattr(
        window_creation_service.agent_profile_service,
        "materialize_agent_profile_for_window",
        fake_materialize_profile,
    )
    monkeypatch.setattr(
        window_creation_service.agent_config_service,
        "apply_agent_config_selection",
        fake_apply,
    )
    monkeypatch.setattr(window_creation_service, "create_window", fake_create_window)
    monkeypatch.setattr(window_creation_service, "schedule_local_window_runtime_start", fake_schedule)

    result = await window_creation_service.create_virtual_window_for_client(
        SimpleNamespace(id=LOCAL_CLIENT_ID, runtime=ClientRuntime.local),
        WindowCreateIn.model_validate(
            {
                "cwd": "/workspace",
                "agent_launch": {
                    "agent": "codex",
                    "command": "codex",
                    "profile_id": "builder",
                    "config": {
                        "agent": "codex",
                        "sections": [
                            {"id": "skills", "items": [{"id": "docker", "enabled": False}]}
                        ],
                    },
                },
            }
        ),
        FakeSession(),
        object(),
        session_factory=FakeSession,
    )

    assert [event[0] for event in events] == ["builtin-profile", "profile", "config", "db", "tmux"]
    assert events[2][1] == ("codex", str(result.window.id), True)
