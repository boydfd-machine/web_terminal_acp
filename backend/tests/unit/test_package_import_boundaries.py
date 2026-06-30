import importlib


def test_exec_split_packages_keep_real_child_module_identity():
    module_pairs = [
        (
            "app.contexts.terminal_runtime.infrastructure.local",
            "app.contexts.terminal_runtime.infrastructure.local.runtime",
        ),
        (
            "app.contexts.terminal_runtime.infrastructure.local",
            "app.contexts.terminal_runtime.infrastructure.local.output_pipe",
        ),
        ("app.contexts.terminal_runtime.api", "app.contexts.terminal_runtime.api.terminal_websocket"),
        ("app.contexts.clients.api.client_agent", "app.contexts.clients.api.client_agent.connection"),
        ("app.client_agent.terminal", "app.client_agent.terminal.public_ops"),
        ("app.client_agent.runner", "app.client_agent.runner.lifecycle"),
        ("app.client_agent.agent_tool_watchers", "app.client_agent.agent_tool_watchers.unified_watcher"),
        (
            "app.contexts.agent_profiles.infrastructure.agent_config_store",
            "app.contexts.agent_profiles.infrastructure.agent_config_store.config_service",
        ),
        (
            "app.contexts.workspace.infrastructure.summary_jobs_repository",
            "app.contexts.workspace.infrastructure.summary_jobs_repository.job_repository",
        ),
        (
            "app.contexts.activity.application.terminal_work_status",
            "app.contexts.activity.application.terminal_work_status.status_service",
        ),
        (
            "app.contexts.terminal_runtime.application.git_worktree_coordinator",
            "app.contexts.terminal_runtime.application.git_worktree_coordinator.tracking_service",
        ),
        (
            "app.contexts.terminal_artifacts.application",
            "app.contexts.terminal_artifacts.application.terminal_execution",
        ),
        ("app.client_agent.shell_hook", "app.client_agent.shell_hook.launchers"),
    ]

    for package_name, child_name in module_pairs:
        package = importlib.import_module(package_name)
        child = importlib.import_module(child_name)

        assert child is not package
        assert child.__name__ == child_name


def test_legacy_child_imports_alias_real_canonical_children():
    module_pairs = [
        (
            "app.contexts.terminal_runtime.infrastructure.local.runtime",
            "app.services.runtime.local.runtime",
        ),
        (
            "app.contexts.terminal_runtime.infrastructure.local.pty_io",
            "app.services.runtime.local.pty_io",
        ),
        (
            "app.contexts.terminal_runtime.infrastructure.local.output_pipe",
            "app.services.runtime.local.output_pipe",
        ),
        (
            "app.contexts.terminal_runtime.api.terminal_websocket",
            "app.routers.terminal.terminal_websocket",
        ),
        (
            "app.contexts.terminal_runtime.api.selection_websocket",
            "app.routers.terminal.selection_websocket",
        ),
        (
            "app.contexts.clients.api.client_agent.connection",
            "app.routers.client_agent.connection",
        ),
        (
            "app.contexts.clients.api.client_agent.message_handlers",
            "app.routers.client_agent.message_handlers",
        ),
    ]

    for canonical_name, legacy_name in module_pairs:
        canonical = importlib.import_module(canonical_name)
        legacy = importlib.import_module(legacy_name)

        assert legacy is canonical


def test_reexported_objects_report_defining_child_modules():
    expectations = [
        (
            "app.contexts.terminal_runtime.infrastructure.local",
            "LocalTerminalRuntime",
            "app.contexts.terminal_runtime.infrastructure.local.runtime",
        ),
        (
            "app.contexts.terminal_runtime.infrastructure.local",
            "pipe_terminal_output",
            "app.contexts.terminal_runtime.infrastructure.local.output_pipe",
        ),
        (
            "app.contexts.terminal_runtime.api",
            "terminal_websocket",
            "app.contexts.terminal_runtime.api.terminal_websocket",
        ),
        (
            "app.client_agent.terminal",
            "ClientTerminalPublicOps",
            "app.client_agent.terminal.public_ops",
        ),
        (
            "app.contexts.agent_profiles.infrastructure.agent_config_store",
            "list_agent_config",
            "app.contexts.agent_profiles.infrastructure.agent_config_store.config_service",
        ),
        (
            "app.contexts.workspace.infrastructure.summary_jobs_repository",
            "enqueue_summary_job",
            "app.contexts.workspace.infrastructure.summary_jobs_repository.job_repository",
        ),
        (
            "app.contexts.activity.application.terminal_work_status",
            "load_work_status",
            "app.contexts.activity.application.terminal_work_status.status_service",
        ),
        (
            "app.client_agent.runner",
            "run_client_agent",
            "app.client_agent.runner.lifecycle",
        ),
        (
            "app.client_agent.shell_hook",
            "build_managed_shell_command",
            "app.client_agent.shell_hook.launchers",
        ),
        (
            "app.contexts.terminal_runtime.application.git_worktree_coordinator",
            "process_worktree_registration",
            "app.contexts.terminal_runtime.application.git_worktree_coordinator.tracking_service",
        ),
        (
            "app.contexts.terminal_artifacts.application",
            "schedule_terminal_artifact_generation",
            "app.contexts.terminal_artifacts.application.generation_service",
        ),
    ]

    for module_name, attribute_name, expected_module_name in expectations:
        module = importlib.import_module(module_name)

        assert getattr(module, attribute_name).__module__ == expected_module_name


def test_legacy_parent_monkeypatches_forward_to_real_children(monkeypatch):
    runner = importlib.import_module("app.client_agent.runner")
    runner_lifecycle = importlib.import_module("app.client_agent.runner.lifecycle")
    local_runtime = importlib.import_module("app.contexts.terminal_runtime.infrastructure.local")
    local_output_pipe = importlib.import_module(
        "app.contexts.terminal_runtime.infrastructure.local.output_pipe"
    )
    terminal_work_status = importlib.import_module(
        "app.contexts.activity.application.terminal_work_status"
    )
    terminal_status_service = importlib.import_module(
        "app.contexts.activity.application.terminal_work_status.status_service"
    )
    git_coordinator = importlib.import_module(
        "app.contexts.terminal_runtime.application.git_worktree_coordinator"
    )
    git_tracking = importlib.import_module(
        "app.contexts.terminal_runtime.application.git_worktree_coordinator.tracking_service"
    )
    summary_jobs = importlib.import_module(
        "app.contexts.workspace.infrastructure.summary_jobs_repository"
    )
    summary_job_status = importlib.import_module(
        "app.contexts.workspace.infrastructure.summary_jobs_repository.job_status"
    )
    terminal_artifacts = importlib.import_module("app.contexts.terminal_artifacts.application")
    terminal_execution = importlib.import_module(
        "app.contexts.terminal_artifacts.application.terminal_execution"
    )

    class FakeRuntime:
        pass

    def fake_dialect(_session):
        return "postgresql"

    async def fake_local_git_worktree_action(action: str, **payload):
        return {"ok": True, "action": action, "payload": payload}

    def fake_get_settings():
        return object()

    monkeypatch.setattr(runner, "ClientTmuxRuntime", FakeRuntime)
    monkeypatch.setattr(local_runtime, "PTY_READ_CHUNK_BYTES", 1234)
    monkeypatch.setattr(terminal_work_status, "_dialect_name", fake_dialect)
    monkeypatch.setattr(git_coordinator, "local_git_worktree_action", fake_local_git_worktree_action)
    monkeypatch.setattr(summary_jobs, "get_settings", fake_get_settings)
    monkeypatch.setattr(terminal_artifacts, "ARTIFACT_AGENT_READY_TIMEOUT_SECONDS", 0.25)

    assert runner_lifecycle.ClientTmuxRuntime is FakeRuntime
    assert local_output_pipe.PTY_READ_CHUNK_BYTES == 1234
    assert terminal_status_service._dialect_name is fake_dialect
    assert git_tracking.local_git_worktree_action is fake_local_git_worktree_action
    assert summary_job_status.get_settings is fake_get_settings
    assert terminal_execution.ARTIFACT_AGENT_READY_TIMEOUT_SECONDS == 0.25
