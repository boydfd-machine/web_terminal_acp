import ast
import os
import subprocess
import sys
from pathlib import Path

from app.services.bootstrap.installer import client_app_file_contents


def _app_module_bundle_paths(module: str) -> tuple[str, ...]:
    if module == "app":
        return ("__init__.py",)
    if not module.startswith("app."):
        return ()
    relative_module = module.removeprefix("app.").replace(".", "/")
    return (f"{relative_module}.py", f"{relative_module}/__init__.py")


def _source_module_exists(backend_app: Path, module: str) -> bool:
    return any((backend_app / path).exists() for path in _app_module_bundle_paths(module))


def _packaged_module_exists(files: dict[str, str], module: str) -> bool:
    return any(path in files for path in _app_module_bundle_paths(module))


def _file_level_app_imports(relative_path: str, source: str, backend_app: Path) -> set[str]:
    tree = ast.parse(source, filename=relative_path)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(
                alias.name
                for alias in node.names
                if alias.name == "app" or alias.name.startswith("app.")
            )
            continue
        if not (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and (node.module == "app" or node.module.startswith("app."))
        ):
            continue
        modules.add(node.module)
        for alias in node.names:
            if alias.name == "*":
                continue
            candidate = f"{node.module}.{alias.name}"
            if _source_module_exists(backend_app, candidate):
                modules.add(candidate)
    return modules


def test_client_app_file_contents_packages_agent_tool_watchers():
    files = client_app_file_contents()

    required_files = {
        "client_agent/git_worktree.py",
        "client_agent/git_worktree_diffs.py",
        "client_agent/gpt_researcher_mcp.py",
        "client_agent/web_terminal_acp_mcp.py",
        "client_agent/aux_terminal.py",
        "client_agent/agent_commands.py",
        "client_agent/process_liveness.py",
        "client_agent/runtime_window.py",
        "client_agent/stale_window_cleanup.py",
        "client_agent/tmux_query.py",
        "client_agent/agent_idle/__init__.py",
        "client_agent/agent_idle/supervisor.py",
        "client_agent/agent_tool_watchers/__init__.py",
        "client_agent/otel_metrics.py",
        "client_agent/agent_tool_watchers/unified_watcher.py",
        "client_agent/agent_tool_watchers/event_collectors.py",
        "client_agent/runner/__init__.py",
        "client_agent/runner/bulk_receive.py",
        "client_agent/runner/cleanup_hooks.py",
        "client_agent/runner/connect_options.py",
        "client_agent/runner/lifecycle.py",
        "client_agent/runner/resume_policy.py",
        "client_agent/runner/runtime_availability.py",
        "client_agent/shell_hook/__init__.py",
        "client_agent/terminal/__init__.py",
        "client_agent/agent_work_presence.py",
        "client_agent/antigravity_watcher.py",
        "client_agent/cursor_watcher.py",
        "client_agent/cursor_statusline.py",
        "client_agent/logging_setup.py",
        "agent_plugins/__init__.py",
        "agent_plugins/builtins.py",
        "agent_plugins/registry.py",
        "agent_plugins/types.py",
        "platform/__init__.py",
        "platform/plugins/__init__.py",
        "platform/plugins/agent_plugins/__init__.py",
        "platform/plugins/agent_plugins/builtins.py",
        "platform/plugins/agent_plugins/registry.py",
        "platform/plugins/agent_plugins/types.py",
        "shared/__init__.py",
        "shared/codex_sessions.py",
        "client_agent/outbound.py",
        "services/agent_config/__init__.py",
        "contexts/agent_profiles/infrastructure/agent_config_store/__init__.py",
        "contexts/agent_profiles/infrastructure/agent_config_store/config_managed_skills.py",
        "contexts/agent_profiles/infrastructure/agent_config_store/config_service.py",
        "contexts/agent_profiles/infrastructure/agent_config_store/config_items.py",
        "contexts/agent_profiles/infrastructure/agent_config_store/config_model_metadata.py",
        "contexts/agent_profiles/infrastructure/agent_config_store/config_system_queries.py",
        "contexts/agent_profiles/infrastructure/builtin_developer_profile_texts.py",
        "contexts/agent_profiles/infrastructure/builtin_profile_specs.py",
        "contexts/agent_profiles/infrastructure/builtin_profiles.py",
        "contexts/agent_profiles/infrastructure/builtin_system_skill_resources.py",
    }
    assert required_files.issubset(files)
    assert "contexts/agent_profiles/infrastructure/profile_config_store.py" in files
    assert "services/agent_profile_manifest.py" in files
    assert "services/agent_profiles.py" in files
    assert "services/terminal_clone.py" in files
    assert "contexts/terminal_runtime/application/command_marker.py" in files
    assert "contexts/terminal_runtime/application/codex_clone.py" in files
    assert "contexts/terminal_runtime/domain/protocol.py" in files
    assert "contexts/terminal_runtime/application/clone.py" in files
    idle_source = files["client_agent/agent_idle/supervisor.py"]
    watcher_source = files["client_agent/agent_tool_watchers/event_collectors.py"]
    presence_source = files["client_agent/agent_work_presence.py"]
    outbound_source = files["client_agent/outbound.py"]
    command_source = files["client_agent/agent_commands.py"]
    assert "def format_agent_command" in command_source
    assert "class AgentIdleSupervisor" in idle_source
    assert "def watch_agent_tool_events" in watcher_source
    assert (
        "from app.client_agent.agent_work_presence import"
        in files["client_agent/agent_tool_watchers/watch_state.py"]
    )
    assert "def detect_agent_work_presence" in presence_source
    assert "app.agent_tools" not in presence_source
    assert "from app.models" not in files["agent_plugins/__init__.py"]
    assert "app.agent_tools" not in files["agent_plugins/types.py"]
    assert "app.agent_tools" not in files["agent_plugins/builtins.py"]
    plugin_source = files["platform/plugins/agent_plugins/builtins.py"]
    assert 'tool_adapter_module="codex"' in plugin_source
    assert 'tool_adapter_class="CodexAdapter"' in plugin_source
    assert "class BulkUploadWriter" in outbound_source


def test_client_app_file_contents_includes_file_level_app_imports():
    files = client_app_file_contents()
    backend_app = Path(__file__).resolve().parents[2] / "app"

    missing = []
    for relative_path, source in files.items():
        if not relative_path.endswith(".py"):
            continue
        for module in sorted(_file_level_app_imports(relative_path, source, backend_app)):
            if _source_module_exists(backend_app, module) and not _packaged_module_exists(
                files,
                module,
            ):
                candidates = " or ".join(_app_module_bundle_paths(module))
                missing.append(f"{relative_path} imports {module}; package {candidates}")

    assert missing == []


def test_packaged_client_bundle_does_not_import_datetime_utc_alias():
    files = client_app_file_contents()
    offenders: list[str] = []
    for relative_path, source in files.items():
        if not relative_path.endswith(".py"):
            continue
        tree = ast.parse(source, filename=relative_path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module != "datetime":
                continue
            if any(alias.name == "UTC" for alias in node.names):
                offenders.append(relative_path)
    assert not offenders, (
        "Bundled client files must not import `UTC` from `datetime` "
        "(Python 3.11+ only). Use `timezone.utc` instead. "
        f"Offenders: {offenders}"
    )


def test_packaged_client_agent_runner_imports_from_isolated_bundle(tmp_path):
    bundle_root = tmp_path / "bundle"
    for relative_path, text in client_app_file_contents().items():
        target = bundle_root / "app" / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    command = (
        "import sys; "
        f"sys.path.insert(0, {str(bundle_root)!r}); "
        "import app.client_agent.runner; "
        "import app.client_agent.gpt_researcher_mcp; "
        "import app.client_agent.web_terminal_acp_mcp; "
        "import app.services.terminal_clone; "
        "import app.services.terminal_command_marker; "
        "import app.services.runtime.protocol; "
        "from app.contexts.agent_profiles.infrastructure import builtin_system_skills; "
        "skill = builtin_system_skills.builtin_system_skill('agent-trace-graph'); "
        "files = {file.path: file.content for file in builtin_system_skills.builtin_system_skill_files(skill)}; "
        "assert 'SKILL.md' in files and 'scripts/render.py' in files; "
        "skill = builtin_system_skills.builtin_system_skill('web-terminal-git-worktree'); "
        "files = {file.path: file.content for file in builtin_system_skills.builtin_system_skill_files(skill)}; "
        "assert 'scripts/setup-git-worktree.sh' in files and 'scripts/merge-agent-branch.py' in files"
    )
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONNOUSERSITE": "1",
    }
    result = subprocess.run(
        [sys.executable, "-I", "-c", command],
        check=False,
        cwd=bundle_root,
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stderr
