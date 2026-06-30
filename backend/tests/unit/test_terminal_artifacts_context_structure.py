import importlib


def test_terminal_artifacts_context_is_canonical_for_legacy_imports():
    context_application = importlib.import_module("app.contexts.terminal_artifacts.application")
    legacy_application = importlib.import_module("app.services.terminal_artifacts")
    assert legacy_application is context_application

    context_api_service = importlib.import_module(
        "app.contexts.terminal_artifacts.application.api_service"
    )
    legacy_api_service = importlib.import_module("app.services.terminal_artifacts.api_service")
    assert legacy_api_service is context_api_service

    context_repository = importlib.import_module(
        "app.contexts.terminal_artifacts.infrastructure.repository"
    )
    legacy_repository = importlib.import_module("app.repositories.terminal_artifacts")
    assert legacy_repository is context_repository

    context_schemas = importlib.import_module("app.contexts.terminal_artifacts.api.schemas")
    legacy_schemas = importlib.import_module("app.schemas.artifacts")
    assert legacy_schemas is context_schemas

    context_domain = importlib.import_module("app.contexts.terminal_artifacts.domain")
    legacy_domain = importlib.import_module("app.domain.terminal_artifacts")
    assert legacy_domain is context_domain
