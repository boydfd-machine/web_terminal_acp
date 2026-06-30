import json
import traceback
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db import Base
from app.models import Client
from app.repositories.clients import create_client
from app.schemas import BootstrapClientIn
from app.services.bootstrap.installer import (
    BootstrapClientNameUnavailable,
    BootstrapConnectionError,
    BootstrapDependencyError,
    BootstrapSecretRedactor,
    build_client_config,
    build_client_config_payload,
    bootstrap_client,
    dependency_check_script,
    _kill_existing_client_processes_command,
)
PRIVATE_KEY = (
    "-----BEGIN OPENSSH PRIVATE KEY-----\nsecret-key-body\n-----END OPENSSH PRIVATE KEY-----"
)
PASSPHRASE = "correct horse battery staple"
TOKEN = "plain-client-token"

def _formatted_exception(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def _uploaded_config(ssh: "FakeSsh") -> dict[str, str]:
    config_path = next(path for path in ssh.uploads if path.endswith("/config.json"))
    return json.loads(ssh.uploads[config_path])


@pytest.fixture
async def db_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield session_factory

    await engine.dispose()


def test_redactor_removes_private_key_passphrase_and_token_from_messages():
    redactor = BootstrapSecretRedactor([PRIVATE_KEY, PASSPHRASE, TOKEN])

    message = f"failed with {PRIVATE_KEY} / {PASSPHRASE} / {TOKEN}"

    redacted = redactor.redact(message)

    assert PRIVATE_KEY not in redacted
    assert PASSPHRASE not in redacted
    assert TOKEN not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_dependency_check_script_checks_required_bins_without_sudo():
    script = dependency_check_script()

    assert "command -v python3" in script
    assert "command -v tmux" in script
    assert "command -v bash" in script
    assert "sys.version_info >= (3, 10)" in script
    assert "python3>=3.10" in script
    assert "python3 -m venv" in script
    assert "-m pip --version" in script
    assert "mktemp -d" in script
    assert "sudo" not in script.lower()


def test_build_client_config_contains_token_only_in_target_config():
    client_id = uuid4()
    config_text = build_client_config(
        SimpleNamespace(id=client_id, name="Remote Dev"),
        token=TOKEN,
        server_url="https://control.example.com/",
        install_path="~/.web-terminal-acp",
    )

    config = json.loads(config_text)

    assert config["client_id"] == str(client_id)
    assert config["token"] == TOKEN
    assert config["server_url"] == "https://control.example.com/"
    assert config["name"] == "Remote Dev"
    assert config["server_id"]
    assert config["server_key"]
    assert config["tmux_pool_session"].startswith("web_terminal_acp_pool_")
    assert config["client_daemon_session"].startswith("web_terminal_acp_client_")
    assert PRIVATE_KEY not in config_text
    assert PASSPHRASE not in config_text


def test_build_client_config_payload_matches_target_config_shape():
    client_id = uuid4()
    payload = build_client_config_payload(
        SimpleNamespace(id=client_id, name="Remote Dev"),
        token=TOKEN,
        server_url="https://control.example.com/",
        install_path="~/.web-terminal-acp",
    )

    assert payload == {
        "client_id": str(client_id),
        "token": TOKEN,
        "server_url": "https://control.example.com/",
        "name": "Remote Dev",
        "install_path": "~/.web-terminal-acp/servers/" + payload["server_key"],
        "server_id": payload["server_id"],
        "server_key": payload["server_key"],
        "tmux_pool_session": (
            "web_terminal_acp_pool_" + payload["server_key"].replace("-", "_")
        ),
        "client_daemon_session": (
            "web_terminal_acp_client_" + payload["server_key"].replace("-", "_")
        ),
    }


def test_kill_existing_client_processes_command_is_scoped_to_server_config():
    command = _kill_existing_client_processes_command(
        "~/.web-terminal-acp/servers/primary-server/config.json"
    )

    assert "[.]web-terminal-acp/servers/primary\\-server/config[.]json" in command
    assert "[.]web-terminal-acp/config[.]json" not in command


class FakeSsh:
    def __init__(
        self, *, existing_config: str | None = None, missing_dependency: str | None = None
    ):
        self.existing_config = existing_config
        self.missing_dependency = missing_dependency
        self.uploads: dict[str, str] = {}
        self.commands: list[str] = []

    def run(self, command: str) -> str:
        self.commands.append(command)
        if "command -v" in command and self.missing_dependency is not None:
            raise BootstrapDependencyError(f"missing dependency: {self.missing_dependency}")
        if "cat ~/.web-terminal-acp/servers/" in command and command.endswith("/config.json"):
            if self.existing_config is None:
                raise FileNotFoundError("missing config")
            return self.existing_config
        return ""

    def upload_text(self, path: str, text: str, mode: int = 0o600) -> None:
        self.uploads[path] = text


@pytest.mark.asyncio
async def test_bootstrap_client_creates_client_and_uploads_config(db_session_factory):
    ssh = FakeSsh()
    payload = BootstrapClientIn(
        name="Remote Dev",
        host="dev.example.com",
        port=22,
        username="alice",
        private_key=PRIVATE_KEY,
        passphrase=PASSPHRASE,
        server_url="https://control.example.com",
    )

    async with db_session_factory() as session:
        result = await bootstrap_client(session, payload, ssh_client_factory=lambda _info: ssh)
        db_client = await session.get(Client, result.client_id)
        await session.commit()

    assert result.reused is False
    assert result.name == "Remote Dev"
    assert result.status == "OFFLINE"
    assert db_client is not None
    assert db_client.last_update_at is not None
    uploaded_config_path = next(path for path in ssh.uploads if path.endswith("/config.json"))
    assert uploaded_config_path.startswith("~/.web-terminal-acp/servers/")
    assert uploaded_config_path != "~/.web-terminal-acp/config.json"
    uploaded_config = ssh.uploads[uploaded_config_path]
    config = json.loads(uploaded_config)
    assert config["client_id"] == str(result.client_id)
    assert config["token"]
    assert config["server_id"]
    assert config["server_key"]
    assert config["install_path"] == "~/.web-terminal-acp/servers/" + config["server_key"]
    assert config["tmux_pool_session"] == (
        "web_terminal_acp_pool_" + config["server_key"].replace("-", "_")
    )
    assert config["client_daemon_session"] == (
        "web_terminal_acp_client_" + config["server_key"].replace("-", "_")
    )
    assert PRIVATE_KEY not in uploaded_config
    assert PASSPHRASE not in uploaded_config
    assert f'{config["install_path"]}/requirements.txt' in ssh.uploads
    assert (
        "app.client_agent.agent_tool_watchers"
        in ssh.uploads[f'{config["install_path"]}/app/app/client_agent/runner/lifecycle.py']
    )
    assert f'{config["install_path"]}/app/app/client_agent/runner/__init__.py' in ssh.uploads
    assert f'{config["install_path"]}/app/app/client_agent/runner/bulk_receive.py' in ssh.uploads
    assert f'{config["install_path"]}/app/app/client_agent/runner/connect_options.py' in ssh.uploads
    assert f'{config["install_path"]}/app/app/client_agent/runner/resume_policy.py' in ssh.uploads
    assert (
        f'{config["install_path"]}/app/app/client_agent/agent_tool_watchers/__init__.py'
        in ssh.uploads
    )
    assert (
        f'{config["install_path"]}/app/app/client_agent/agent_tool_watchers/unified_watcher.py'
        in ssh.uploads
    )
    assert f'{config["install_path"]}/app/app/client_agent/agent_commands.py' in ssh.uploads
    assert f'{config["install_path"]}/app/app/client_agent/antigravity_watcher.py' in ssh.uploads
    assert f'{config["install_path"]}/app/app/client_agent/codex_watcher.py' in ssh.uploads
    assert f'{config["install_path"]}/app/app/client_agent/cursor_watcher.py' in ssh.uploads
    assert any(
        f'rm -rf \'{config["install_path"]}/app/app\''
        in command
        and f'mkdir -p \'{config["install_path"]}/app/app\'' in command
        for command in ssh.commands
    )
    assert any(
        f'mkdir -p {config["install_path"]}/npm-global/bin' in command
        for command in ssh.commands
    )
    assert any(
        f'python3 -m venv {config["install_path"]}/venv' in command for command in ssh.commands
    )
    daemon_commands = "\n".join(ssh.commands)
    assert "systemctl --user enable --now" in daemon_commands
    assert config["client_daemon_session"] in daemon_commands
    assert "<key>KeepAlive</key>" in daemon_commands
    assert any("pgrep -f" in command for command in ssh.commands)
    assert any(
        f'PATH="$HOME/.web-terminal-acp/servers/{config["server_key"]}/npm-global/bin:$PATH"'
        in command
        for command in ssh.commands
    )
    assert any(
        f'{config["install_path"]}/venv/bin/python -m app.client_agent' in command
        for command in ssh.commands
    )
    assert any(
        f'--config {config["install_path"]}/config.json' in command
        for command in ssh.commands
    )


@pytest.mark.asyncio
async def test_bootstrap_client_reuses_existing_remote_config(db_session_factory):
    client_id = uuid4()
    existing_config = json.dumps(
        {
            "client_id": str(client_id),
            "token": TOKEN,
            "server_url": "https://control.example.com",
            "name": "Existing Dev",
            "install_path": "~/.web-terminal-acp",
        }
    )
    ssh = FakeSsh(existing_config=existing_config)
    payload = BootstrapClientIn(
        name="Existing Dev",
        host="dev.example.com",
        port=22,
        username="alice",
        private_key=PRIVATE_KEY,
        passphrase=None,
        server_url="https://control.example.com",
    )

    async with db_session_factory() as session:
        result = await bootstrap_client(session, payload, ssh_client_factory=lambda _info: ssh)
        db_client = await session.get(Client, result.client_id)
        await session.commit()

    assert result.reused is True
    assert result.client_id == client_id
    assert db_client is not None
    assert db_client.last_update_at is not None
    assert _uploaded_config(ssh)["token"] == TOKEN


@pytest.mark.asyncio
async def test_bootstrap_client_reuses_existing_remote_name_without_config(db_session_factory):
    ssh = FakeSsh()
    payload = BootstrapClientIn(
        name="Named Dev",
        host="dev.example.com",
        port=22,
        username="alice",
        private_key=PRIVATE_KEY,
        passphrase=None,
        server_url="https://control.example.com",
    )

    async with db_session_factory() as session:
        existing_client, old_token = await create_client(
            session,
            name="Named Dev",
            hostname="old-host",
            install_path="/old/path",
        )
        existing_id = existing_client.id
        old_hash = existing_client.token_hash
        await session.flush()

        result = await bootstrap_client(session, payload, ssh_client_factory=lambda _info: ssh)
        db_client = await session.get(Client, existing_id)
        await session.commit()

    uploaded_config = _uploaded_config(ssh)
    assert result.reused is True
    assert result.client_id == existing_id
    assert db_client is not None
    assert db_client.token_hash != old_hash
    assert uploaded_config["client_id"] == str(existing_id)
    assert uploaded_config["token"] != old_token


@pytest.mark.asyncio
async def test_bootstrap_client_prefers_requested_name_when_existing_config_points_elsewhere(
    db_session_factory,
):
    existing_config_id = uuid4()
    existing_config = json.dumps(
        {
            "client_id": str(existing_config_id),
            "token": TOKEN,
            "server_url": "https://control.example.com",
            "name": "Old Config",
            "install_path": "~/.web-terminal-acp",
        }
    )
    ssh = FakeSsh(existing_config=existing_config)
    payload = BootstrapClientIn(
        name="Named Dev",
        host="dev.example.com",
        port=22,
        username="alice",
        private_key=PRIVATE_KEY,
        passphrase=None,
        server_url="https://control.example.com",
    )

    async with db_session_factory() as session:
        configured_client, _old_config_token = await create_client(
            session,
            name="Old Config",
            token=TOKEN,
            hostname="old-host",
            install_path="/old/path",
        )
        configured_client.id = existing_config_id
        named_client, named_old_token = await create_client(
            session,
            name="Named Dev",
            hostname="named-old-host",
            install_path="/named/old/path",
        )
        named_id = named_client.id
        named_old_hash = named_client.token_hash
        await session.flush()

        result = await bootstrap_client(session, payload, ssh_client_factory=lambda _info: ssh)
        db_named_client = await session.get(Client, named_id)
        await session.commit()

    uploaded_config = _uploaded_config(ssh)
    assert result.reused is True
    assert result.client_id == named_id
    assert db_named_client is not None
    assert db_named_client.token_hash != named_old_hash
    assert uploaded_config["client_id"] == str(named_id)
    assert uploaded_config["token"] not in {TOKEN, named_old_token}


@pytest.mark.asyncio
async def test_bootstrap_client_rejects_existing_config_owned_by_another_user(db_session_factory):
    client_id = uuid4()
    existing_config = json.dumps(
        {
            "client_id": str(client_id),
            "token": TOKEN,
            "server_url": "https://control.example.com",
            "name": "Existing Dev",
            "install_path": "~/.web-terminal-acp",
        }
    )
    ssh = FakeSsh(existing_config=existing_config)
    payload = BootstrapClientIn(
        name="Existing Dev",
        host="dev.example.com",
        port=22,
        username="alice",
        private_key=PRIVATE_KEY,
        passphrase=None,
        server_url="https://control.example.com",
    )

    async with db_session_factory() as session:
        existing_client, _ = await create_client(
            session,
            name="Existing Dev",
            token=TOKEN,
            owner_user_id="alice",
        )
        existing_client.id = client_id
        await session.flush()

        with pytest.raises(BootstrapClientNameUnavailable):
            await bootstrap_client(
                session,
                payload,
                owner_user_id="bob",
                ssh_client_factory=lambda _info: ssh,
            )


@pytest.mark.asyncio
async def test_bootstrap_client_redacts_connection_errors(db_session_factory):
    def fail_factory(_info):
        raise BootstrapConnectionError(f"auth failed {PRIVATE_KEY} {PASSPHRASE}")

    payload = BootstrapClientIn(
        name="Remote Dev",
        host="dev.example.com",
        port=22,
        username="alice",
        private_key=PRIVATE_KEY,
        passphrase=PASSPHRASE,
        server_url="https://control.example.com",
    )

    async with db_session_factory() as session:
        with pytest.raises(BootstrapConnectionError) as exc_info:
            await bootstrap_client(session, payload, ssh_client_factory=fail_factory)

    message = str(exc_info.value)
    assert PRIVATE_KEY not in message
    assert PASSPHRASE not in message


@pytest.mark.asyncio
async def test_bootstrap_client_traceback_redacts_secret_connection_cause(db_session_factory):
    def fail_factory(_info):
        raise ValueError(f"auth failed {PRIVATE_KEY} {PASSPHRASE}")

    payload = BootstrapClientIn(
        name="Remote Dev",
        host="dev.example.com",
        port=22,
        username="alice",
        private_key=PRIVATE_KEY,
        passphrase=PASSPHRASE,
        server_url="https://control.example.com",
    )

    async with db_session_factory() as session:
        with pytest.raises(BootstrapConnectionError) as exc_info:
            await bootstrap_client(session, payload, ssh_client_factory=fail_factory)

    formatted = _formatted_exception(exc_info.value)
    assert PRIVATE_KEY not in formatted
    assert PASSPHRASE not in formatted


@pytest.mark.asyncio
async def test_bootstrap_client_traceback_redacts_generated_token_cause(db_session_factory):
    class FailingUploadSsh(FakeSsh):
        def __init__(self):
            super().__init__()
            self.attempted_config: str | None = None

        def upload_text(self, path: str, text: str, mode: int = 0o600) -> None:
            if path.endswith("/config.json"):
                self.attempted_config = text
                token = json.loads(text)["token"]
                raise RuntimeError(f"upload failed with token {token}")
            super().upload_text(path, text, mode=mode)

    ssh = FailingUploadSsh()
    payload = BootstrapClientIn(
        name="Remote Dev",
        host="dev.example.com",
        port=22,
        username="alice",
        private_key=PRIVATE_KEY,
        passphrase=PASSPHRASE,
        server_url="https://control.example.com",
    )

    async with db_session_factory() as session:
        with pytest.raises(BootstrapConnectionError) as exc_info:
            await bootstrap_client(session, payload, ssh_client_factory=lambda _info: ssh)

    assert ssh.attempted_config is not None
    generated_token = json.loads(ssh.attempted_config)["token"]
    formatted = _formatted_exception(exc_info.value)
    assert PRIVATE_KEY not in formatted
    assert PASSPHRASE not in formatted
    assert generated_token not in formatted
