import importlib


def test_agent_profiles_context_is_canonical_for_legacy_imports():
    module_pairs = [
        ("app.contexts.agent_profiles.api.routes", "app.routers.agent_profiles"),
        ("app.contexts.agent_profiles.application.api_service", "app.services.agent_profiles_api"),
        (
            "app.contexts.agent_profiles.application.capabilities",
            "app.services.agent_client_capabilities",
        ),
        (
            "app.contexts.agent_profiles.application.config_projection",
            "app.services.agent_config_projection",
        ),
        (
            "app.contexts.agent_profiles.application.manifest_service",
            "app.services.agent_profile_manifest",
        ),
        ("app.contexts.agent_profiles.infrastructure.profile_store", "app.services.agent_profiles"),
        (
            "app.contexts.agent_profiles.infrastructure.agent_config_store",
            "app.services.agent_config",
        ),
    ]
    for context_path, legacy_path in module_pairs:
        context_module = importlib.import_module(context_path)
        legacy_module = importlib.import_module(legacy_path)
        assert legacy_module is context_module

    context_domain = importlib.import_module("app.contexts.agent_profiles.domain")
    legacy_domain = importlib.import_module("app.domain.agent_profiles")
    assert legacy_domain is context_domain


def test_agent_profiles_schemas_are_owned_by_context():
    context_schemas = importlib.import_module("app.contexts.agent_profiles.api.schemas")
    schemas = importlib.import_module("app.schemas")

    for name in (
        "AgentClientListOut",
        "AgentClientOut",
        "AgentConfigOut",
        "AgentConfigToggleIn",
        "AgentProfileCreateIn",
        "AgentProfileListOut",
        "AgentProfileOut",
        "AgentProfileUpdateIn",
    ):
        assert getattr(schemas, name) is getattr(context_schemas, name)
