import importlib


def test_platform_modules_are_canonical_for_legacy_imports():
    module_pairs = [
        ("app.platform.auth_routes", "app.routers.auth"),
        ("app.platform.cache_backend", "app.services.cache_backend"),
        ("app.platform.polling_response_cache", "app.services.polling_response_cache"),
        ("app.platform.search_index", "app.services.search_index"),
        ("app.platform.search_routes", "app.routers.search"),
        ("app.platform.ui_events", "app.services.ui_events"),
        ("app.platform.ui_events_routes", "app.routers.ui_events"),
        ("app.platform.ui_settings_repository", "app.repositories.ui_settings"),
        ("app.platform.ui_settings_routes", "app.routers.ui_settings"),
        ("app.platform.ingest", "app.services.ingest"),
        ("app.platform.ingest.claude_watcher", "app.services.ingest.claude_watcher"),
        ("app.platform.ingest.codex_receiver", "app.services.ingest.codex_receiver"),
        ("app.platform.ingest.normalizers", "app.services.ingest.normalizers"),
        ("app.platform.plugins.agent_plugins", "app.agent_plugins"),
        ("app.platform.plugins.agent_plugins.builtins", "app.agent_plugins.builtins"),
        ("app.platform.plugins.agent_plugins.registry", "app.agent_plugins.registry"),
        ("app.platform.plugins.agent_plugins.types", "app.agent_plugins.types"),
        ("app.platform.plugins.agent_tools", "app.agent_tools"),
        ("app.platform.plugins.agent_tools.common", "app.agent_tools.common"),
        ("app.platform.plugins.agent_tools.registry", "app.agent_tools.registry"),
        ("app.platform.plugins.agent_tools.types", "app.agent_tools.types"),
        ("app.platform.plugins.agent_tools.user_input", "app.agent_tools.user_input"),
        ("app.platform.plugins.artifact_plugins", "app.artifact_plugins"),
        (
            "app.platform.plugins.artifact_plugins.agent_pitfalls",
            "app.artifact_plugins.agent_pitfalls",
        ),
        (
            "app.platform.plugins.artifact_plugins.agent_trace_graph",
            "app.artifact_plugins.agent_trace_graph",
        ),
        (
            "app.platform.plugins.artifact_plugins.review_agent_artifacts",
            "app.artifact_plugins.review_agent_artifacts",
        ),
        ("app.platform.plugins.artifact_plugins.registry", "app.artifact_plugins.registry"),
        ("app.platform.plugins.artifact_plugins.types", "app.artifact_plugins.types"),
        ("app.platform.plugins.agent_tools.adapters", "app.agent_tools.adapters"),
        (
            "app.platform.plugins.agent_tools.adapters.antigravity_cli",
            "app.agent_tools.adapters.antigravity_cli",
        ),
        (
            "app.platform.plugins.agent_tools.adapters.antigravity_subagents",
            "app.agent_tools.adapters.antigravity_subagents",
        ),
        (
            "app.platform.plugins.agent_tools.adapters.claude_code",
            "app.agent_tools.adapters.claude_code",
        ),
        (
            "app.platform.plugins.agent_tools.adapters.claude_code_subagents",
            "app.agent_tools.adapters.claude_code_subagents",
        ),
        ("app.platform.plugins.agent_tools.adapters.codex", "app.agent_tools.adapters.codex"),
        (
            "app.platform.plugins.agent_tools.adapters.cursor_cli",
            "app.agent_tools.adapters.cursor_cli",
        ),
    ]
    for platform_path, legacy_path in module_pairs:
        platform_module = importlib.import_module(platform_path)
        legacy_module = importlib.import_module(legacy_path)
        assert legacy_module is platform_module


def test_shared_modules_are_canonical_for_legacy_imports():
    module_pairs = [
        ("app.shared.llm_json", "app.services.llm_json"),
        ("app.shared.redaction", "app.services.redaction"),
    ]
    for shared_path, legacy_path in module_pairs:
        shared_module = importlib.import_module(shared_path)
        legacy_module = importlib.import_module(legacy_path)
        assert legacy_module is shared_module


def test_platform_search_schemas_are_canonical_for_legacy_schema_exports():
    platform_schemas = importlib.import_module("app.platform.search_schemas")
    schemas = importlib.import_module("app.schemas")
    legacy_misc = importlib.import_module("app.schemas.misc")

    for name in ("SearchOut", "SearchResultOut"):
        assert getattr(schemas, name) is getattr(platform_schemas, name)
        assert getattr(legacy_misc, name) is getattr(platform_schemas, name)


def test_platform_auth_schemas_are_canonical_for_legacy_schema_exports():
    platform_schemas = importlib.import_module("app.platform.auth_schemas")
    schemas = importlib.import_module("app.schemas")
    legacy_clients = importlib.import_module("app.schemas.clients")

    for name in ("LoginIn", "LoginOut", "AuthStatusOut", "KeycloakPublicConfigOut", "CaptchaOut"):
        assert getattr(schemas, name) is getattr(platform_schemas, name)
        assert getattr(legacy_clients, name) is getattr(platform_schemas, name)


def test_platform_common_schemas_are_canonical_for_legacy_schema_exports():
    platform_schemas = importlib.import_module("app.platform.common_schemas")
    schemas = importlib.import_module("app.schemas")
    legacy_common = importlib.import_module("app.schemas.common")

    for name in (
        "WindowTitle",
        "WindowText",
        "WindowTitleTag",
        "WindowStatusIn",
        "AgentKindIn",
        "AgentConfigSectionKindIn",
        "ClientName",
        "ClientStatusOut",
        "ClientRuntimeOut",
        "BootstrapHost",
        "BootstrapUsername",
        "BootstrapPrivateKey",
        "BootstrapServerUrl",
        "LoginSecret",
        "CaptchaId",
        "CaptchaAnswer",
        "RegistrationKey",
        "AgentConfigSelectionItemIn",
        "AgentConfigSelectionSectionIn",
        "AgentConfigSelectionIn",
        "AgentLaunchIn",
    ):
        assert getattr(schemas, name) is getattr(platform_schemas, name)
        assert getattr(legacy_common, name) is getattr(platform_schemas, name)


def test_platform_ui_settings_schemas_are_canonical_for_legacy_schema_exports():
    platform_schemas = importlib.import_module("app.platform.ui_settings_schemas")
    schemas = importlib.import_module("app.schemas")
    legacy_misc = importlib.import_module("app.schemas.misc")

    for name in ("CustomQuickKeyOut", "CustomQuickKeysOut", "CustomQuickKeysPutIn"):
        assert getattr(schemas, name) is getattr(platform_schemas, name)
        assert getattr(legacy_misc, name) is getattr(platform_schemas, name)
