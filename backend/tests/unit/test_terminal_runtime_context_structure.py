import importlib


def test_terminal_runtime_context_is_canonical_for_legacy_imports():
    module_pairs = [
        ("app.contexts.terminal_runtime.api", "app.routers.terminal"),
        ("app.contexts.terminal_runtime.api.runtime_dependencies", "app.routers.terminal.runtime_dependencies"),
        ("app.contexts.terminal_runtime.api.terminal_websocket", "app.routers.terminal.terminal_websocket"),
        ("app.contexts.terminal_runtime.api.selection_websocket", "app.routers.terminal.selection_websocket"),
        ("app.contexts.terminal_runtime.api.local_recording_routes", "app.routers.terminal_local_recording"),
        ("app.contexts.terminal_runtime.api.aux_terminal_routes", "app.routers.aux_terminal"),
        ("app.contexts.terminal_runtime.application.aux_terminal", "app.services.aux_terminal"),
        ("app.contexts.terminal_runtime.application.broker", "app.services.runtime.broker"),
        ("app.contexts.terminal_runtime.application.clone", "app.services.terminal_clone"),
        ("app.contexts.terminal_runtime.application.command_marker", "app.services.terminal_command_marker"),
        ("app.contexts.terminal_runtime.application.connection_registry", "app.services.runtime.connection_registry"),
        (
            "app.contexts.terminal_runtime.application.git_worktree_agent_markers",
            "app.services.git_worktree_agent_markers",
        ),
        (
            "app.contexts.terminal_runtime.application.git_worktree_client",
            "app.services.git_worktree_client",
        ),
        (
            "app.contexts.terminal_runtime.application.git_worktree_coordinator",
            "app.services.git_worktree_coordinator",
        ),
        ("app.contexts.terminal_runtime.application.local_session", "app.services.runtime.local_session"),
        ("app.contexts.terminal_runtime.application.offline_monitor", "app.services.runtime.offline_monitor"),
        ("app.contexts.terminal_runtime.application.output_recorder", "app.services.terminal_output_recorder"),
        ("app.contexts.terminal_runtime.application.runtime_binding", "app.services.terminal_runtime_binding"),
        ("app.contexts.terminal_runtime.application.selection", "app.services.terminal_selection"),
        ("app.contexts.terminal_runtime.application.stream_markers", "app.services.terminal_stream_markers"),
        ("app.contexts.terminal_runtime.application.subscriber_writer", "app.services.runtime.subscriber_writer"),
        ("app.contexts.terminal_runtime.application.terminal_bridge", "app.services.terminal_bridge"),
        ("app.contexts.terminal_runtime.application.window_reconciler", "app.services.window_reconciler"),
        ("app.contexts.terminal_runtime.application.worktree_marker", "app.services.terminal_worktree_marker"),
        ("app.contexts.terminal_runtime.domain.protocol", "app.services.runtime.protocol"),
        ("app.contexts.terminal_runtime.domain.git_worktree_ops", "app.services.git_worktree_ops"),
        ("app.contexts.terminal_runtime.domain.types", "app.services.runtime.types"),
        (
            "app.contexts.terminal_runtime.infrastructure.git_worktree_repository",
            "app.repositories.git_worktree",
        ),
        ("app.contexts.terminal_runtime.infrastructure.pty_control", "app.services.runtime.pty_control"),
        ("app.contexts.terminal_runtime.infrastructure.tmux_manager", "app.services.tmux_manager"),
        ("app.contexts.terminal_runtime.infrastructure.tmux_paths", "app.services.tmux_paths"),
        ("app.contexts.terminal_runtime.infrastructure.tmux_targets", "app.services.tmux_targets"),
        ("app.contexts.terminal_runtime.infrastructure.local", "app.services.runtime.local"),
        ("app.contexts.terminal_runtime.infrastructure.local.pty_io", "app.services.runtime.local.pty_io"),
        ("app.contexts.terminal_runtime.infrastructure.local.runtime", "app.services.runtime.local.runtime"),
        ("app.contexts.terminal_runtime.infrastructure.remote", "app.services.runtime.remote"),
        ("app.contexts.terminal_runtime.infrastructure.remote.agent_ops", "app.services.runtime.remote.agent_ops"),
        ("app.contexts.terminal_runtime.infrastructure.remote.file_ops", "app.services.runtime.remote.file_ops"),
        ("app.contexts.terminal_runtime.infrastructure.remote.helpers", "app.services.runtime.remote.helpers"),
        ("app.contexts.terminal_runtime.infrastructure.remote.terminal_ops", "app.services.runtime.remote.terminal_ops"),
    ]
    for context_path, legacy_path in module_pairs:
        context_module = importlib.import_module(context_path)
        legacy_module = importlib.import_module(legacy_path)
        assert legacy_module is context_module
