import importlib


def test_activity_context_is_canonical_for_legacy_imports():
    module_pairs = [
        ("app.contexts.activity.api.terminal_notifications_routes", "app.routers.terminal_notifications"),
        ("app.contexts.activity.api.terminal_recents_routes", "app.routers.terminal_recents"),
        ("app.contexts.activity.api.traces_routes", "app.routers.traces"),
        ("app.contexts.activity.application.agent_activity_projection", "app.services.agent_activity_projection"),
        ("app.contexts.activity.application.agent_event_ingest", "app.services.agent_event_ingest"),
        ("app.contexts.activity.application.agent_work_presence", "app.services.agent_work_presence"),
        ("app.contexts.activity.domain.event_kinds", "app.services.event_kinds"),
        ("app.contexts.activity.application.terminal_notifications", "app.services.terminal_notifications"),
        ("app.contexts.activity.application.terminal_time_ranges", "app.services.terminal_time_ranges"),
        ("app.contexts.activity.application.terminal_work_status", "app.services.terminal_work_status"),
        ("app.contexts.activity.application.window_activity", "app.services.window_activity_api"),
        (
            "app.contexts.activity.application.window_git_worktree_activity",
            "app.services.window_git_worktree_activity",
        ),
        ("app.contexts.activity.application.window_runtime_tags", "app.services.window_runtime_tags"),
        ("app.contexts.activity.domain.terminal_time_range", "app.domain.terminal_time_range"),
        ("app.contexts.activity.infrastructure.ai_sessions_repository", "app.repositories.ai_sessions"),
        ("app.contexts.activity.infrastructure.events_repository", "app.repositories.events"),
        ("app.contexts.activity.infrastructure.terminal_recents_repository", "app.repositories.terminal_recents"),
    ]
    for context_path, legacy_path in module_pairs:
        context_module = importlib.import_module(context_path)
        legacy_module = importlib.import_module(legacy_path)
        assert legacy_module is context_module


def test_activity_schemas_are_owned_by_context():
    context_schemas = importlib.import_module("app.contexts.activity.api.schemas")
    schemas = importlib.import_module("app.schemas")

    for name in (
        "AgentEventOut",
        "AgentEventProjectionOut",
        "AgentSessionOut",
        "ClientWindowsActivityOut",
        "GitWorktreeActivityOut",
        "GlobalTerminalRecentOut",
        "GlobalTerminalRecentPageOut",
        "IngestEventOut",
        "ManualWorkStatusIn",
        "TerminalNotificationAckIn",
        "TerminalNotificationListOut",
        "TerminalNotificationOut",
        "TerminalRecentOut",
        "TerminalRecentPageOut",
        "TerminalRecentTouchIn",
        "WindowActivityOut",
        "WorkStatusOut",
    ):
        assert getattr(schemas, name) is getattr(context_schemas, name)
