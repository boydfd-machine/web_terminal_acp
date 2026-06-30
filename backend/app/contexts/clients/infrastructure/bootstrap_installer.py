from __future__ import annotations
import asyncio
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import shlex
from typing import Iterator, Protocol
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.client_agent.client_daemon import start_client_daemon_command
from app.config import get_settings
from app.contexts.clients.api.schemas import BootstrapClientIn
from app.contexts.clients.domain.server_identity import RemoteClientInstance
from app.contexts.clients.infrastructure.bootstrap_ssh import (
    SshClient,
    SshCommandError,
    SshConnectionInfo,
)
from app.contexts.clients.infrastructure.repository import (
    ClientNameUnavailable,
    create_or_rotate_remote_client_by_name,
    get_client,
    get_client_by_name,
    hash_client_token,
    verify_client_token,
)
from app.models import Client, ClientRuntime, ClientStatus
DEFAULT_INSTALL_PATH = "~/.web-terminal-acp"
AGENT_REQUIREMENTS = "pydantic>=2.8.0\nwebsockets>=13.1\n"
class BootstrapDependencyError(RuntimeError):
    """The remote target is missing a required bootstrap dependency."""
class BootstrapConnectionError(RuntimeError):
    """The server could not connect to or operate on the remote SSH target."""
class BootstrapClientNameUnavailable(RuntimeError):
    """The requested client name belongs to a different owner."""
@dataclass(frozen=True)
class BootstrapResult:
    client_id: UUID
    name: str
    status: str
    reused: bool
class BootstrapSshClient(Protocol):
    def run(self, command: str) -> str: ...
    def upload_text(self, remote_path: str, text: str, mode: int = 0o600) -> None: ...
class BootstrapSecretRedactor:
    def __init__(self, secrets: list[str | None]) -> None:
        self._secrets = sorted(
            {secret for secret in secrets if secret}, key=lambda secret: len(secret), reverse=True
        )
    def redact(self, value: object) -> str:
        text = str(value)
        for secret in self._secrets:
            text = text.replace(secret, "[REDACTED]")
        text = re.sub(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            "[REDACTED]",
            text,
            flags=re.DOTALL,
        )
        return re.sub(r"\b\S*token\S*\b", "[REDACTED]", text, flags=re.IGNORECASE)


def dependency_check_script() -> str:
    return """#!/usr/bin/env bash
set -u
missing=""
command -v python3 >/dev/null 2>&1 || missing="$missing python3"
command -v tmux >/dev/null 2>&1 || missing="$missing tmux"
command -v bash >/dev/null 2>&1 || missing="$missing bash"
if command -v python3 >/dev/null 2>&1 && ! python3 - <<'PY' >/dev/null 2>&1
import sys

raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
  missing="$missing python3>=3.10"
fi
venv_test="$(mktemp -d 2>/dev/null || true)"
if [ -z "$venv_test" ] || ! python3 -m venv "$venv_test/venv" >/dev/null 2>&1 || ! "$venv_test/venv/bin/python" -m pip --version >/dev/null 2>&1; then
  missing="$missing python3-venv"
fi
rm -rf "$venv_test"
if [ -n "$missing" ]; then
  echo "missing dependencies:$missing" >&2
  exit 42
fi
"""


def build_client_config(client: Client, *, token: str, server_url: str, install_path: str) -> str:
    return json.dumps(
        build_client_config_payload(
            client,
            token=token,
            server_url=server_url,
            install_path=install_path,
        ),
        indent=2,
        sort_keys=True,
    )


def build_client_config_payload(
    client: Client,
    *,
    token: str,
    server_url: str,
    install_path: str,
) -> dict[str, str]:
    instance = RemoteClientInstance.from_server_id(
        get_settings().web_terminal_server_id,
        base_install_path=install_path,
    )
    return {
        "client_id": str(client.id),
        "token": token,
        "server_url": server_url,
        "name": client.name,
        "install_path": instance.install_path,
        "server_id": instance.server_id,
        "server_key": instance.server_key,
        "tmux_pool_session": instance.tmux_pool_session,
        "client_daemon_session": instance.client_daemon_session,
    }


async def bootstrap_client(
    session: AsyncSession,
    payload: BootstrapClientIn,
    *,
    owner_user_id: str | None = None,
    ssh_client_factory=SshClient,
) -> BootstrapResult:
    redactor = BootstrapSecretRedactor([payload.private_key, payload.passphrase])
    info = SshConnectionInfo(
        host=payload.host,
        port=payload.port,
        username=payload.username,
        private_key=payload.private_key,
        passphrase=payload.passphrase,
    )
    instance = _remote_client_instance()

    try:
        existing_config_text = await asyncio.to_thread(
            _check_dependencies_and_read_existing_config,
            info,
            ssh_client_factory,
            instance,
        )
        client, token, reused = await _resolve_client(
            session,
            payload,
            existing_config_text,
            install_path=instance.install_path,
            owner_user_id=owner_user_id,
        )
        redactor = BootstrapSecretRedactor([payload.private_key, payload.passphrase, token])
        config_text = build_client_config(
            client,
            token=token,
            server_url=payload.server_url,
            install_path=DEFAULT_INSTALL_PATH,
        )
        await asyncio.to_thread(
            _upload_and_start_client,
            info,
            ssh_client_factory,
            config_text,
            instance,
        )
        client.last_update_at = datetime.now(UTC)
        await session.flush()
        return BootstrapResult(
            client_id=client.id,
            name=client.name,
            status=client.status.value,
            reused=reused,
        )
    except BootstrapDependencyError as exc:
        raise BootstrapDependencyError(redactor.redact(exc)) from None
    except BootstrapConnectionError as exc:
        raise BootstrapConnectionError(redactor.redact(exc)) from None
    except ClientNameUnavailable as exc:
        raise BootstrapClientNameUnavailable(redactor.redact(exc)) from None
    except BootstrapClientNameUnavailable:
        raise
    except Exception as exc:
        raise BootstrapConnectionError(redactor.redact(exc)) from None


def _check_dependencies_and_read_existing_config(
    info: SshConnectionInfo,
    ssh_client_factory,
    instance: RemoteClientInstance,
) -> str | None:
    with _connect(info, ssh_client_factory) as ssh:
        try:
            ssh.run(dependency_check_script())
        except BootstrapDependencyError:
            raise
        except SshCommandError as exc:
            if exc.exit_status == 42:
                raise BootstrapDependencyError(
                    exc.stderr.strip() or "missing bootstrap dependency"
                ) from None
            raise BootstrapConnectionError(str(exc)) from None

        try:
            return ssh.run(f"cat {instance.config_path}")
        except Exception:
            return None


def _upload_and_start_client(
    info: SshConnectionInfo,
    ssh_client_factory,
    config_text: str,
    instance: RemoteClientInstance,
) -> None:
    with _connect(info, ssh_client_factory) as ssh:
        ssh.upload_text(instance.config_path, config_text, mode=0o600)
        ssh.upload_text(instance.requirements_path, AGENT_REQUIREMENTS, mode=0o644)
        ssh.run(_reset_client_app_root_command(instance))
        for remote_path, text in _client_app_files(instance).items():
            ssh.upload_text(remote_path, text, mode=0o644)
        ssh.run(_install_agent_dependencies_command(instance))
        ssh.run(_start_daemon_command(instance))


@contextmanager
def _connect(info: SshConnectionInfo, ssh_client_factory) -> Iterator[BootstrapSshClient]:
    try:
        client = ssh_client_factory(info)
        manager = client if hasattr(client, "__enter__") else nullcontext(client)
        with manager as connected:
            yield connected
    except BootstrapDependencyError:
        raise
    except BootstrapConnectionError:
        raise
    except Exception as exc:
        raise BootstrapConnectionError(str(exc)) from None


async def _resolve_client(
    session: AsyncSession,
    payload: BootstrapClientIn,
    existing_config_text: str | None,
    *,
    install_path: str,
    owner_user_id: str | None = None,
) -> tuple[Client, str, bool]:
    existing = _parse_existing_config(existing_config_text)
    if existing is not None:
        client_id, token = existing
        client = await get_client(session, client_id)
        if client is None:
            named_client = await get_client_by_name(session, payload.name)
            if named_client is not None:
                rotated_client, _token, _reused = await create_or_rotate_remote_client_by_name(
                    session,
                    name=payload.name,
                    token=token,
                    hostname=payload.host,
                    install_path=install_path,
                    owner_user_id=owner_user_id,
                )
                return rotated_client, token, True
            client = Client(
                id=client_id,
                name=payload.name,
                status=ClientStatus.OFFLINE,
                token_hash=hash_client_token(token),
                owner_user_id=owner_user_id,
                hostname=payload.host,
                install_path=install_path,
                runtime=ClientRuntime.remote,
            )
            session.add(client)
            await session.flush()
            return client, token, True
        if verify_client_token(token, client.token_hash):
            if client.owner_user_id is not None and client.owner_user_id != owner_user_id:
                raise ClientNameUnavailable("client belongs to another user")
            named_client = await get_client_by_name(session, payload.name)
            if named_client is not None and named_client.id != client.id:
                (
                    rotated_client,
                    rotated_token,
                    _reused,
                ) = await create_or_rotate_remote_client_by_name(
                    session,
                    name=payload.name,
                    hostname=payload.host,
                    install_path=install_path,
                    owner_user_id=owner_user_id,
                )
                return rotated_client, rotated_token, True
            client.name = payload.name
            client.hostname = payload.host
            client.install_path = install_path
            if owner_user_id is not None or client.owner_user_id is None:
                client.owner_user_id = owner_user_id
            client.runtime = ClientRuntime.remote
            await session.flush()
            return client, token, True

    client, token, reused = await create_or_rotate_remote_client_by_name(
        session,
        name=payload.name,
        hostname=payload.host,
        install_path=install_path,
        owner_user_id=owner_user_id,
    )
    return client, token, reused


def _parse_existing_config(config_text: str | None) -> tuple[UUID, str] | None:
    if not config_text:
        return None
    try:
        data = json.loads(config_text)
        client_id = UUID(str(data["client_id"]))
        token = str(data["token"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if not token:
        return None
    return client_id, token


def _remote_client_instance() -> RemoteClientInstance:
    return RemoteClientInstance.from_server_id(
        get_settings().web_terminal_server_id,
        base_install_path=DEFAULT_INSTALL_PATH,
    )


def _client_app_files(instance: RemoteClientInstance) -> dict[str, str]:
    return {
        f"{instance.app_path}/app/{relative_path}": text
        for relative_path, text in client_app_file_contents().items()
    }


def client_app_file_contents() -> dict[str, str]:
    backend_app = Path(__file__).resolve().parents[3]
    source_files = [
        "__init__.py",
        "version.py",
        "agent_plugins/__init__.py",
        "agent_plugins/builtins.py",
        "agent_plugins/registry.py",
        "agent_plugins/types.py",
        "platform/__init__.py",
        "platform/plugins/__init__.py",
        "platform/plugins/agent_plugins/__init__.py",
        "platform/plugins/agent_plugins/builtins.py",
        "platform/plugins/agent_plugins/registry.py",
        "platform/plugins/agent_plugins/shared_cache.py",
        "platform/plugins/agent_plugins/types.py",
        "shared/__init__.py",
        "shared/codex_sessions.py",
        "shared/llm_json.py",
        "shared/redaction.py",
        "client_agent/__init__.py",
        "client_agent/__main__.py",
        "client_agent/client_daemon.py",
        "client_agent/config.py",
        "client_agent/logging_setup.py",
        "client_agent/gpt_researcher_mcp.py",
        "client_agent/web_terminal_acp_mcp.py",
        "client_agent/aux_terminal.py",
        "client_agent/agent_commands.py",
        "client_agent/cursor_official_models.py",
        "client_agent/git_worktree.py",
        "client_agent/git_worktree_diffs.py",
        "client_agent/outbound.py",
        "client_agent/process_liveness.py",
        "client_agent/runtime_window.py",
        "client_agent/stale_window_cleanup.py",
        "client_agent/tmux_query.py",
        "client_agent/otel_metrics.py",
        "client_agent/agent_work_presence.py",
        "client_agent/ai_events.py",
        "client_agent/antigravity_watcher.py",
        "client_agent/codex_watcher.py",
        "client_agent/cursor_watcher.py",
        "client_agent/cursor_statusline.py",
        "client_agent/tmux_runtime.py",
        "client_agent/updater.py",
        "contexts/__init__.py",
        "contexts/clients/__init__.py",
        "contexts/clients/domain/__init__.py",
        "contexts/clients/domain/client.py",
        "contexts/clients/domain/server_identity.py",
        "contexts/agent_profiles/__init__.py",
        "contexts/agent_profiles/application/__init__.py",
        "contexts/agent_profiles/application/manifest_service.py",
        "contexts/agent_profiles/infrastructure/__init__.py",
        "contexts/agent_profiles/infrastructure/builtin_developer_profile_texts.py",
        "contexts/agent_profiles/infrastructure/builtin_profile_texts.py",
        "contexts/agent_profiles/infrastructure/builtin_profile_specs.py",
        "contexts/agent_profiles/infrastructure/builtin_profiles.py",
        "contexts/agent_profiles/infrastructure/builtin_system_skill_resources.py",
        "contexts/agent_profiles/infrastructure/builtin_system_skill_types.py",
        "contexts/agent_profiles/infrastructure/builtin_system_skills.py",
        "contexts/agent_profiles/infrastructure/profile_config_store.py",
        "contexts/agent_profiles/infrastructure/profile_store.py",
        "resources/__init__.py",
        "resources/system_skills/__init__.py",
        "contexts/terminal_runtime/__init__.py",
        "contexts/terminal_runtime/application/__init__.py",
        "contexts/terminal_runtime/application/codex_clone.py",
        "contexts/terminal_runtime/application/command_marker.py",
        "contexts/terminal_runtime/application/clone.py",
        "contexts/terminal_runtime/domain/__init__.py",
        "contexts/terminal_runtime/domain/protocol.py",
        "services/__init__.py",
        "services/agent_profile_manifest.py",
        "services/agent_profiles.py",
        "services/terminal_clone.py",
        "services/terminal_command_marker.py",
        "services/runtime/protocol.py",
    ]
    source_dirs = [
        "client_agent/agent_idle",
        "client_agent/agent_tool_watchers",
        "client_agent/runner",
        "client_agent/shell_hook",
        "client_agent/terminal",
        "contexts/agent_profiles/domain",
        "contexts/agent_profiles/infrastructure/agent_config_store",
        "services/agent_config",
    ]
    resource_dirs = [
        "resources/system_skills",
    ]
    return {
        relative_path: (backend_app / relative_path).read_text(encoding="utf-8")
        for relative_path in _client_app_source_paths(
            backend_app,
            source_files,
            source_dirs,
            resource_dirs,
        )
    }


def _client_app_source_paths(
    backend_app: Path,
    source_files: list[str],
    source_dirs: list[str],
    resource_dirs: list[str],
) -> list[str]:
    paths = list(source_files)
    for source_dir in source_dirs:
        paths.extend(
            str(path.relative_to(backend_app))
            for path in sorted((backend_app / source_dir).rglob("*.py"))
        )
    for resource_dir in resource_dirs:
        paths.extend(
            str(path.relative_to(backend_app))
            for path in sorted((backend_app / resource_dir).rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts
        )
    return sorted(dict.fromkeys(paths))


def _reset_client_app_root_command(instance: RemoteClientInstance) -> str:
    app_root = f"{instance.app_path}/app"
    return f"rm -rf {shlex.quote(app_root)} && mkdir -p {shlex.quote(app_root)}"


def _install_agent_dependencies_command(instance: RemoteClientInstance) -> str:
    return (
        f"mkdir -p {instance.install_path}/npm-global/bin && "
        f"python3 -m venv {instance.venv_path} && "
        f"{instance.venv_path}/bin/python -m pip install --upgrade pip && "
        f"{instance.venv_path}/bin/python -m pip install -r {instance.requirements_path}"
    )


def _start_daemon_command(instance: RemoteClientInstance) -> str:
    return start_client_daemon_command(
        install_path=instance.install_path,
        app_path=instance.app_path,
        python_path=f"{instance.venv_path}/bin/python",
        config_path=instance.config_path,
        daemon_name=instance.client_daemon_session,
        npm_bin_path=f"$HOME/.web-terminal-acp/servers/{instance.server_key}/npm-global/bin",
    )


def _kill_existing_client_processes_command(config_path: str) -> str:
    server_key = config_path.rsplit("/", 2)[-2]
    pattern = (
        r"python.*-m app[.]client_agent.*--config "
        rf".*/[.]web-terminal-acp/servers/{re.escape(server_key)}/"
        r"config[.]json"
    )
    return (
        f"for pid in $(pgrep -f {shlex.quote(pattern)} || true); do "
        'if [ "$pid" != "$$" ]; then kill "$pid" >/dev/null 2>&1 || true; fi; '
        "done; "
        "sleep 1; "
        f"for pid in $(pgrep -f {shlex.quote(pattern)} || true); do "
        'if [ "$pid" != "$$" ]; then kill -9 "$pid" >/dev/null 2>&1 || true; fi; '
        "done"
    )
