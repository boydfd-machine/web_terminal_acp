import importlib


def test_clients_context_is_canonical_for_legacy_imports():
    context_api_service = importlib.import_module(
        "app.contexts.clients.application.api_service"
    )
    legacy_api_service = importlib.import_module("app.services.clients.api_service")
    assert legacy_api_service is context_api_service

    context_client_agent = importlib.import_module("app.contexts.clients.api.client_agent")
    legacy_client_agent = importlib.import_module("app.routers.client_agent")
    assert legacy_client_agent is context_client_agent
    for suffix in ("connection", "message_handlers", "bulk_websocket", "single_websocket"):
        context_submodule = importlib.import_module(f"app.contexts.clients.api.client_agent.{suffix}")
        legacy_submodule = importlib.import_module(f"app.routers.client_agent.{suffix}")
        assert context_submodule is not context_client_agent
        assert legacy_submodule is context_submodule

    context_bootstrap_installer = importlib.import_module(
        "app.contexts.clients.infrastructure.bootstrap_installer"
    )
    legacy_bootstrap_installer = importlib.import_module("app.services.bootstrap.installer")
    assert legacy_bootstrap_installer is context_bootstrap_installer

    context_bootstrap_ssh = importlib.import_module(
        "app.contexts.clients.infrastructure.bootstrap_ssh"
    )
    legacy_bootstrap_ssh = importlib.import_module("app.services.bootstrap.ssh")
    assert legacy_bootstrap_ssh is context_bootstrap_ssh

    context_client_update = importlib.import_module(
        "app.contexts.clients.application.client_update"
    )
    legacy_client_update = importlib.import_module("app.services.client_update")
    assert legacy_client_update is context_client_update

    context_direct_registration = importlib.import_module(
        "app.contexts.clients.application.direct_registration"
    )
    legacy_direct_registration = importlib.import_module("app.services.direct_registration")
    assert legacy_direct_registration is context_direct_registration

    context_direct_registration_script = importlib.import_module(
        "app.contexts.clients.application.direct_registration_script"
    )
    legacy_direct_registration_script = importlib.import_module(
        "app.services.direct_registration_script"
    )
    assert legacy_direct_registration_script is context_direct_registration_script

    context_repository = importlib.import_module(
        "app.contexts.clients.infrastructure.repository"
    )
    legacy_repository = importlib.import_module("app.repositories.clients")
    assert legacy_repository is context_repository

    context_registration_keys = importlib.import_module(
        "app.contexts.clients.infrastructure.registration_keys_repository"
    )
    legacy_registration_keys = importlib.import_module(
        "app.repositories.client_registration_keys"
    )
    assert legacy_registration_keys is context_registration_keys

    context_schemas = importlib.import_module("app.contexts.clients.api.schemas")
    legacy_schemas = importlib.import_module("app.schemas.clients")
    assert legacy_schemas is context_schemas

    context_domain = importlib.import_module("app.contexts.clients.domain")
    legacy_domain = importlib.import_module("app.domain.clients")
    assert legacy_domain is context_domain
