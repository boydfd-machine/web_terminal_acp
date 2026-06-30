from app.models import VirtualWindow
from app.services.runtime.types import RuntimeWindow
from app.services.terminal_runtime_binding import RuntimeWindowBinding


def test_runtime_window_binding_maps_local_window() -> None:
    binding = RuntimeWindowBinding.from_virtual_window(
        VirtualWindow(
            tmux_session="web-terminal",
            tmux_window_id="@7",
            tmux_window_index="3",
            cwd="/workspace",
            shell_command="codex",
        )
    )

    assert binding is not None
    assert binding.is_local_window is True
    assert binding.is_remote_window is False
    assert binding.runtime_window == RuntimeWindow(
        session_id="web-terminal",
        window_id="@7",
        window_index="3",
        cwd="/workspace",
        shell_command="codex",
    )
    assert binding.runtime_persistence_fields() == {
        "tmux_session": "web-terminal",
        "tmux_window_id": "@7",
        "tmux_window_index": "3",
        "remote_session_id": None,
        "remote_window_id": None,
        "cwd": "/workspace",
        "shell_command": "codex",
    }


def test_runtime_window_binding_maps_remote_window() -> None:
    binding = RuntimeWindowBinding.from_virtual_window(
        VirtualWindow(
            remote_session_id="remote-session",
            remote_window_id="remote-window",
            cwd="/remote",
            shell_command="claude",
        )
    )

    assert binding is not None
    assert binding.is_local_window is False
    assert binding.is_remote_window is True
    assert binding.runtime_window == RuntimeWindow(
        session_id="remote-session",
        window_id="remote-window",
        cwd="/remote",
        shell_command="claude",
    )
    assert binding.runtime_persistence_fields() == {
        "tmux_session": None,
        "tmux_window_id": None,
        "tmux_window_index": None,
        "remote_session_id": "remote-session",
        "remote_window_id": "remote-window",
        "cwd": "/remote",
        "shell_command": "claude",
    }


def test_runtime_window_binding_is_absent_until_runtime_identifiers_exist() -> None:
    assert RuntimeWindowBinding.from_virtual_window(VirtualWindow(title="pending")) is None


def test_runtime_window_binding_replaces_runtime_window_immutably() -> None:
    binding = RuntimeWindowBinding(
        RuntimeWindow(session_id="web-terminal", window_id="@1"),
        "local",
    )
    updated = binding.with_runtime_window(RuntimeWindow(session_id="web-terminal", window_id="@2"))

    assert binding.runtime_window.window_id == "@1"
    assert updated.runtime_window.window_id == "@2"
    assert updated.scope == "local"
