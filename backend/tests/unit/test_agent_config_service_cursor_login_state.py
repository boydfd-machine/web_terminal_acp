# ruff: noqa: F403,F405
from tests.unit.test_agent_config_service_support import *


def test_apply_agent_config_selection_links_cursor_root_state_files(tmp_path: Path) -> None:
    cursor_home = tmp_path / ".cursor"
    cursor_home.mkdir()
    (cursor_home / "1").write_text("", encoding="utf-8")
    (cursor_home / "managed").mkdir()
    (cursor_home / "managed" / "team").mkdir()

    apply_agent_config_selection(
        AgentConfigSelection(agent="cursor", sections=[]),
        window_id="window-1",
        home=tmp_path,
    )

    managed_cursor = tmp_path / ".web-terminal-acp" / "cursor-homes" / "window-1"
    assert (managed_cursor / "1").resolve() == cursor_home / "1"
    assert (managed_cursor / "managed").resolve() == cursor_home / "managed"
