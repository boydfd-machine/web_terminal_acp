from datetime import UTC, datetime

from app.domain.clients import BearerToken, ClientUpdateCompletion
from app.contexts.clients.domain.server_identity import (
    RemoteClientInstance,
    server_id_from_environment,
    server_key_from_id,
)
from app.contexts.clients.application.patches import client_patch_from_payload
from app.schemas import ClientPatchIn, ClientUpdateCompleteIn


def test_bearer_token_parses_only_valid_bearer_authorization():
    assert BearerToken.parse("Bearer client-token") == BearerToken("client-token")
    assert BearerToken.parse("bearer client-token") == BearerToken("client-token")
    assert BearerToken.parse(None) is None
    assert BearerToken.parse("Basic client-token") is None
    assert BearerToken.parse("Bearer") is None
    assert BearerToken.parse("Bearer ") is None


def test_client_patch_preserves_payload_field_intent():
    omitted = client_patch_from_payload(ClientPatchIn())
    renamed = client_patch_from_payload(ClientPatchIn(name="Desk Mini"))

    assert omitted.name is None
    assert renamed.name == "Desk Mini"


def test_update_completion_builds_callback_response_payload():
    payload = ClientUpdateCompleteIn(job_id="job-1")
    completion = ClientUpdateCompletion.now(job_id=payload.job_id)

    assert completion.job_id == "job-1"
    assert completion.completed_at.tzinfo is UTC
    assert completion.response_payload(client_id="client-1") == {
        "client_id": "client-1",
        "job_id": "job-1",
        "completed_at": completion.completed_at,
    }


def test_update_completion_allows_missing_job_id():
    completion = ClientUpdateCompletion(
        job_id=None,
        completed_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert completion.response_payload(client_id="client-1")["job_id"] is None


def test_server_id_from_environment_prefers_configured_value():
    assert server_id_from_environment("  Primary Server  ", hostname="dev-host") == "Primary Server"


def test_server_id_from_environment_falls_back_to_hostname():
    assert server_id_from_environment("", hostname="dev-host") == "dev-host"
    assert server_id_from_environment(None, hostname="dev-host") == "dev-host"


def test_remote_client_instance_uses_server_scoped_paths_and_sessions():
    instance = RemoteClientInstance.from_server_id(
        "Primary Server!",
        base_install_path="~/.web-terminal-acp",
    )

    assert instance.server_id == "Primary Server!"
    assert instance.server_key == "primary-server"
    assert instance.install_path == "~/.web-terminal-acp/servers/primary-server"
    assert instance.config_path == "~/.web-terminal-acp/servers/primary-server/config.json"
    assert instance.client_daemon_session == "web_terminal_acp_client_primary_server"
    assert instance.tmux_pool_session == "web_terminal_acp_pool_primary_server"


def test_remote_client_instance_uses_stable_hash_when_server_id_has_no_slug_characters():
    instance = RemoteClientInstance.from_server_id("服务器一", base_install_path="/opt/acp")

    assert instance.server_key.startswith("server-")
    assert instance.install_path == f"/opt/acp/servers/{instance.server_key}"
    assert instance.client_daemon_session == (
        "web_terminal_acp_client_" + instance.server_key.replace("-", "_")
    )


def test_server_key_from_id_keeps_long_server_ids_distinct():
    first = server_key_from_id("control-" + ("a" * 80) + "-one")
    second = server_key_from_id("control-" + ("a" * 80) + "-two")

    assert first != second
    assert len(first) <= 48
    assert len(second) <= 48
