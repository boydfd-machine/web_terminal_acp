import pytest

from app.client_agent.agent_commands import agent_command_with_official_model_flag
from app.client_agent.cursor_official_models import list_cursor_official_models
from app.contexts.agent_profiles.domain.cursor_official_models import (
    CURSOR_OFFICIAL_MODEL_PRESET_ID,
    parse_cursor_official_models_output,
)
from app.contexts.windows.api.schemas import WindowCreateIn
from app.contexts.windows.application.launch_plans import local_window_launch_plan
from app.platform.common_schemas import AgentLaunchIn, AgentModelSelectionIn


def test_parse_cursor_official_models_output() -> None:
    text = """Available models

auto - Auto
composer-2.5 - Composer 2.5 (current)
gpt-5.3-codex - Codex 5.3
"""
    assert parse_cursor_official_models_output(text) == [
        {"id": "auto", "label": "Auto"},
        {"id": "composer-2.5", "label": "Composer 2.5 (current)"},
        {"id": "gpt-5.3-codex", "label": "Codex 5.3"},
    ]


def test_list_cursor_official_models_prefers_proxychains_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_which(command: str) -> str | None:
        if command == "proxychains4":
            return "/usr/bin/proxychains4"
        if command == "cursor-agent":
            return "~/.local/bin/cursor-agent"
        if command == "agent":
            return "~/.local/bin/agent"
        return None

    def fake_run(args, **kwargs):
        calls.append(list(args))

        class Result:
            returncode = 0
            stdout = """Available models\n\nauto - Auto\ncomposer-2.5 - Composer 2.5\n"""

        if args[0] == "/usr/bin/proxychains4":
            Result.stdout = """Available models\n\nauto - Auto\ngpt-5.3-codex - Codex 5.3\n"""
        return Result()

    monkeypatch.setattr("app.client_agent.cursor_official_models.shutil.which", fake_which)
    monkeypatch.setattr("app.client_agent.cursor_official_models.subprocess.run", fake_run)

    assert list_cursor_official_models() == [
        {"id": "auto", "label": "Auto"},
        {"id": "gpt-5.3-codex", "label": "Codex 5.3"},
    ]
    assert calls == [["/usr/bin/proxychains4", "-q", "~/.local/bin/cursor-agent", "models"]]


def test_agent_command_with_official_model_flag_inserts_model_after_agent() -> None:
    assert (
        agent_command_with_official_model_flag("agent", "composer-2.5")
        == "agent --model composer-2.5"
    )


def test_agent_command_with_official_model_flag_replaces_existing_model() -> None:
    assert (
        agent_command_with_official_model_flag("agent --model auto", "gpt-5.3-codex")
        == "agent --model gpt-5.3-codex"
    )


def test_local_window_launch_plan_applies_cursor_official_model_to_shell_command() -> None:
    payload = WindowCreateIn(
        cwd="/tmp/project",
        agent_launch=AgentLaunchIn(
            agent="cursor",
            command="agent",
            model_selection=AgentModelSelectionIn(
                preset_id=CURSOR_OFFICIAL_MODEL_PRESET_ID,
                model="composer-2.5",
            ),
        ),
    )
    plan = local_window_launch_plan(payload, default_shell="/bin/bash")
    assert plan.shell_command == "agent --model composer-2.5"
    assert plan.agent_model_settings is None
    assert plan.agent_model_selection is not None
    assert plan.agent_model_selection.preset_id == CURSOR_OFFICIAL_MODEL_PRESET_ID
