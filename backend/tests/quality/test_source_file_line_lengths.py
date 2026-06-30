from __future__ import annotations

from pathlib import Path


MAX_SOURCE_LINES = 500
OVERSIZED_SOURCE_BASELINE = {
    "backend/app/client_agent/agent_tool_watchers/event_collectors.py": 512,
    "backend/app/client_agent/agent_tool_watchers/unified_watcher.py": 511,
    "backend/app/client_agent/runner/runtime_message_handlers.py": 529,
    "backend/app/client_agent/shell_hook/bash_hooks.py": 566,
    "backend/app/client_agent/shell_hook/launchers.py": 575,
    "backend/app/contexts/agent_profiles/infrastructure/agent_config_store/config_service.py": 532,
    "backend/app/contexts/activity/application/terminal_work_status/agent_activity_queries.py": 504,
    "backend/app/contexts/agent_profiles/infrastructure/agent_config_store/config_model_settings.py": 521,
    "backend/app/contexts/agent_profiles/infrastructure/profile_store.py": 539,
    "backend/app/contexts/clients/infrastructure/bootstrap_installer.py": 515,
    "backend/app/contexts/terminal_artifacts/application/generation_service.py": 553,
    "backend/app/contexts/windows/api/window_detail_routes.py": 549,
    "backend/app/contexts/workspace/api/schemas.py": 506,
    "backend/app/contexts/workspace/application/project_todo_artifacts.py": 521,
    "backend/app/contexts/workspace/application/project_todo_completion_verification.py": 522,
    "backend/tests/integration/test_auth_api.py": 628,
    "backend/tests/integration/test_client_agent_ws_ai_event_ingest.py": 879,
    "backend/tests/integration/test_project_todo_artifacts_api.py": 510,
    "backend/tests/integration/test_window_api_fakes.py": 501,
    "backend/tests/integration/test_window_api_agent_record_chat_pagination.py": 501,
    "backend/tests/unit/test_agent_config_service_model_settings.py": 832,
    "backend/tests/unit/test_agent_config_service_codex_window_profiles.py": 602,
    "backend/tests/unit/test_bootstrap_installer.py": 504,
    "backend/tests/unit/test_client_agent_agent_tool_watchers_codex_claude_offsets.py": 522,
    "backend/tests/unit/test_client_agent_agent_tool_watchers_history_and_cursor.py": 501,
    "backend/tests/unit/test_client_agent_runner_runtime_lifecycle.py": 526,
    "backend/tests/unit/test_models_schema_constraints.py": 539,
    "backend/tests/unit/test_project_todo_completion_verification.py": 708,
    "backend/tests/unit/test_project_todo_artifacts.py": 507,
    "backend/tests/unit/test_remote_runtime_terminal_and_file_requests.py": 510,
    "frontend/src/App.tsx": 512,
    "frontend/src/components/AppToolbar.tsx": 519,
    "frontend/src/components/ProjectTodoCreateForm.tsx": 531,
    "frontend/src/components/TerminalCreateModal.tsx": 507,
    "frontend/src/hooks/useAppPresentationController.ts": 573,
    "frontend/tests/apiProjectTodos.test.ts": 506,
    "frontend/tests/appSidebarSelection.test.tsx": 696,
    "frontend/tests/projectFilesView.test.tsx": 592,
    "frontend/tests/terminalCreateModal.mergesSystemSkillAndMcpDefaults.test.tsx": 705,
    "frontend/tests/uiEvents.test.ts": 507,
}
SOURCE_EXTENSIONS = {".cjs", ".js", ".jsx", ".mjs", ".py", ".ts", ".tsx"}
SKIPPED_PARTS = {
    ".claude",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".web-terminal-acp",
    "build",
    "dist",
    "node_modules",
    "playwright-report",
}


def test_source_files_stay_under_line_limit() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    oversized = {}

    for path in _source_files(repo_root):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_SOURCE_LINES:
            oversized[path.relative_to(repo_root).as_posix()] = line_count

    assert oversized == OVERSIZED_SOURCE_BASELINE


def _source_files(root: Path) -> list[Path]:
    source_files: list[Path] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        for path in sorted(directory.iterdir()):
            if path.name in SKIPPED_PARTS:
                continue
            if path.is_dir():
                pending.append(path)
            elif path.suffix in SOURCE_EXTENSIONS:
                source_files.append(path)
    return sorted(source_files)
