import importlib


def test_windows_context_is_canonical_for_legacy_imports():
    module_pairs = [
        ("app.contexts.windows.api", "app.routers.windows"),
        (
            "app.contexts.windows.infrastructure.repository",
            "app.repositories.windows",
        ),
        ("app.contexts.windows.domain", "app.domain.windows"),
        ("app.contexts.windows.application", "app.services.windows"),
    ]
    for context_path, legacy_path in module_pairs:
        context_module = importlib.import_module(context_path)
        legacy_module = importlib.import_module(legacy_path)
        assert legacy_module is context_module


def test_windows_schemas_are_owned_by_contexts():
    windows_schemas = importlib.import_module("app.contexts.windows.api.schemas")
    activity_schemas = importlib.import_module("app.contexts.activity.api.schemas")
    agent_profile_schemas = importlib.import_module("app.contexts.agent_profiles.api.schemas")
    workspace_schemas = importlib.import_module("app.contexts.workspace.api.schemas")
    legacy_windows = importlib.import_module("app.schemas.windows")
    legacy_agent_records = importlib.import_module("app.schemas.agent_records")
    schemas = importlib.import_module("app.schemas")

    windows_owned_names = (
        "AgentChatMessageOut",
        "AgentChatRecordOut",
        "AgentRecordOut",
        "CommandHistoryItemOut",
        "CommandHistoryOut",
        "GitWorktreeRunListOut",
        "GitWorktreeRunOut",
        "SummaryJobOut",
        "SummaryJobRetryIn",
        "TreeFolderOut",
        "TreeWindowOut",
        "WindowCloneIn",
        "WindowCreateIn",
        "WindowOut",
        "WindowPatchIn",
        "WindowTitleHistoryItemOut",
        "WindowTitleHistoryOut",
    )
    for name in windows_owned_names:
        assert getattr(schemas, name) is getattr(windows_schemas, name)
        assert getattr(legacy_windows, name, None) is getattr(windows_schemas, name)
        assert getattr(legacy_agent_records, name, None) is getattr(windows_schemas, name)

    for name in (
        "ClientWindowsActivityOut",
        "GitWorktreeActivityOut",
        "ManualWorkStatusIn",
        "TerminalNotificationAckIn",
        "TerminalNotificationListOut",
        "TerminalNotificationOut",
        "WindowActivityOut",
        "WorkStatusOut",
    ):
        assert getattr(schemas, name) is getattr(activity_schemas, name)
        assert getattr(legacy_windows, name, None) is getattr(activity_schemas, name)

    for name in (
        "AgentEventOut",
        "AgentEventProjectionOut",
        "AgentSessionOut",
        "GitWorktreeActivityOut",
        "WorkStatusOut",
    ):
        assert getattr(schemas, name) is getattr(activity_schemas, name)
        assert getattr(legacy_agent_records, name, None) is getattr(activity_schemas, name)

    for name in (
        "AgentClientListOut",
        "AgentClientOut",
        "AgentConfigItemOut",
        "AgentConfigOut",
        "AgentConfigSectionOut",
        "AgentConfigToggleIn",
        "AgentProfileCreateIn",
        "AgentProfileListOut",
        "AgentProfileOut",
        "AgentProfileUpdateIn",
    ):
        assert getattr(schemas, name) is getattr(agent_profile_schemas, name)
        assert getattr(legacy_agent_records, name, None) is getattr(agent_profile_schemas, name)

    for name in (
        "FolderCreateIn",
        "FolderOut",
        "ProjectBrowseRootListOut",
        "ProjectBrowseRootOut",
        "ProjectFileContentOut",
        "ProjectFileEntryOut",
        "ProjectFileListOut",
        "ProjectFileSaveIn",
        "ProjectFileUploadIn",
        "ProjectFileUploadOut",
        "ProjectOut",
        "TerminalProjectOut",
    ):
        assert getattr(schemas, name) is getattr(workspace_schemas, name)
        assert getattr(legacy_windows, name, None) is getattr(workspace_schemas, name)
