# ruff: noqa: F403, F405
from tests.unit.test_terminal_artifact_service_support import *

@pytest.mark.asyncio
async def test_run_artifact_prompt_uses_snapshot_polling_for_remote_clients(monkeypatch) -> None:
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_AGENT_READY_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_AGENT_READY_SETTLE_SECONDS", 0.0)
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_OUTPUT_IDLE_GRACE_SECONDS", 0.0)
    client = type("Client", (), {"id": uuid4(), "runtime": ClientRuntime.remote})()
    source_window = type("Window", (), {"shell_command": "codex"})()
    ephemeral_window = type("Window", (), {"id": uuid4()})()
    runtime_window = RuntimeWindow(session_id="remote-session", window_id="@7")
    broker = TerminalBroker()
    request_timeouts = []

    class RemoteStyleRuntime:
        def __init__(self) -> None:
            self.inputs = []
            self.captures = 0

        async def attach(self, window, sender, *, local_window_id=None, selection_callback=None, view_id=None):
            raise AssertionError("artifact generation must not attach a remote shadow view")

        async def detach(self, window, *, local_window_id=None, view_id=None):
            return None

        async def send_input_direct(self, window, data, *, local_window_id=None):
            self.inputs.append((data, local_window_id))

        async def capture_output_bytes(self, window, *, local_window_id=None, view_id=None, history_lines=None):
            assert history_lines == terminal_artifact_service.ARTIFACT_CAPTURE_HISTORY_LINES
            self.captures += 1
            if self.inputs:
                return (
                    b"OpenAI Codex (v0.136.0)\nmodel:       gpt-5.5 xhigh\n\n\xe2\x80\xba "
                    b'{"task":"demo","goals":[],"nodes":[],"edges":[]}'
                )
            return b"OpenAI Codex (v0.136.0)\nmodel:       gpt-5.5 xhigh\n\n\xe2\x80\xba "

        async def resize(self, window, *, cols, rows, local_window_id=None, view_id=None):
            raise AssertionError("artifact generation must not resize a remote shadow view")

    runtime = RemoteStyleRuntime()

    def remote_runtime_factory(**kwargs):
        request_timeouts.append(kwargs["request_timeout"])
        return runtime

    monkeypatch.setattr(terminal_artifact_service, "RemoteRuntime", remote_runtime_factory)

    output = await _run_artifact_prompt(
        client,
        source_window,
        ephemeral_window,
        runtime_window,
        "artifact prompt",
        output_path=None,
        is_complete=lambda value: '"task":"demo"' in value,
        session_factory=unused_session_factory,
        terminal_broker=broker,
        tmux_manager=object(),
        registry=object(),
    )

    assert '"task":"demo"' in output
    assert runtime.inputs == [(b"artifact prompt\x1b[13u", ephemeral_window.id)]
    assert request_timeouts == [terminal_artifact_service.ARTIFACT_REMOTE_RUNTIME_REQUEST_TIMEOUT_SECONDS]

@pytest.mark.asyncio
async def test_run_artifact_prompt_polls_terminal_snapshot_when_attach_is_silent(monkeypatch) -> None:
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_AGENT_READY_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_AGENT_READY_SETTLE_SECONDS", 0.0)
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_OUTPUT_IDLE_GRACE_SECONDS", 0.0)
    events = []

    class SnapshotBroker:
        def runtime_for(self, client_id):
            return object()

        async def subscribe(self, client_id, window_id, sender):
            raise AssertionError("artifact generation must not add a broker output subscription")

        async def attach(self, client_id, window_id, runtime_window, *, output_callback=None, view_id):
            raise AssertionError("artifact generation must not attach a hidden terminal view")

        async def resize(self, *args, **kwargs):
            raise AssertionError("artifact generation must not resize a hidden terminal view")

        async def capture_output_bytes(self, client_id, window_id, runtime_window, *, history_lines=None):
            assert history_lines == terminal_artifact_service.ARTIFACT_CAPTURE_HISTORY_LINES
            events.append(("capture", window_id))
            if any(event[0] == "send" for event in events):
                return (
                    b"OpenAI Codex (v0.136.0)\nmodel:       gpt-5.5 xhigh\n\n\xe2\x80\xba "
                    b'{"task":"demo","goals":[],"nodes":[],"edges":[]}'
                )
            return b"OpenAI Codex (v0.136.0)\nmodel:       gpt-5.5 xhigh\n\n\xe2\x80\xba "

        async def send_input_direct(self, client_id, window_id, runtime_window, data):
            events.append(("send", data))

        async def unsubscribe(self, *args, **kwargs):
            raise AssertionError("artifact generation must not unsubscribe a broker output subscription")

    client = type("Client", (), {"id": "client-1", "runtime": ClientRuntime.local})()
    source_window = type("Window", (), {"shell_command": "codex"})()
    ephemeral_window = type("Window", (), {"id": uuid4()})()
    runtime_window = type("RuntimeWindow", (), {})()

    output = await _run_artifact_prompt(
        client,
        source_window,
        ephemeral_window,
        runtime_window,
        "artifact prompt",
        output_path=None,
        is_complete=lambda value: '"task":"demo"' in value,
        session_factory=unused_session_factory,
        terminal_broker=SnapshotBroker(),
        tmux_manager=object(),
        registry=None,
    )

    assert '"task":"demo"' in output
    assert "capture" in [event[0] for event in events]
    assert [event[0] for event in events].index("capture") < [event[0] for event in events].index("send")

@pytest.mark.asyncio
async def test_run_artifact_prompt_fails_instead_of_sending_before_agent_ready(monkeypatch) -> None:
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_AGENT_READY_TIMEOUT_SECONDS", 0.05)
    sent = []

    class FakeBroker:
        def runtime_for(self, client_id):
            return object()

        async def subscribe(self, client_id, window_id, sender):
            raise AssertionError("artifact generation must not add a broker output subscription")

        async def attach(self, client_id, window_id, runtime_window, *, view_id):
            raise AssertionError("artifact generation must not attach a hidden terminal view")

        async def resize(self, *args, **kwargs):
            return None

        async def capture_output_bytes(self, client_id, window_id, runtime_window, *, history_lines=None):
            assert history_lines == terminal_artifact_service.ARTIFACT_CAPTURE_HISTORY_LINES
            return b""

        async def send_input_direct(self, client_id, window_id, runtime_window, data):
            sent.append(data)

        async def unsubscribe(self, *args, **kwargs):
            return None

    client = type("Client", (), {"id": "client-1", "runtime": ClientRuntime.local})()
    source_window = type("Window", (), {"shell_command": "codex"})()
    ephemeral_window = type("Window", (), {"id": uuid4()})()
    runtime_window = type("RuntimeWindow", (), {})()

    with pytest.raises(TimeoutError, match="no interactive prompt was detected"):
        await _run_artifact_prompt(
            client,
            source_window,
            ephemeral_window,
            runtime_window,
            "artifact prompt",
            output_path=None,
            is_complete=lambda value: False,
            session_factory=unused_session_factory,
            terminal_broker=FakeBroker(),
            tmux_manager=object(),
            registry=None,
        )

    assert sent == []

@pytest.mark.asyncio
async def test_create_ephemeral_local_window_starts_cloned_agent_resume_command(monkeypatch) -> None:
    events = []

    class FakeTmuxManager:
        async def create_window(self, cwd, shell_command, *, client_id, window_id):
            events.append(("tmux", shell_command))
            return type(
                "Target",
                (),
                {
                    "session": "pool",
                    "window_id": "@3",
                    "window_index": "4",
                    "cwd": cwd,
                    "shell_command": shell_command,
                },
            )()

    async def fake_create_window(session, client_id, cwd, shell_command, **kwargs):
        events.append(("db", kwargs["derived_context"]))
        return type(
            "Window",
            (),
            {
                "id": kwargs["window_id"],
                "status": None,
                "tmux_session": kwargs["tmux_session"],
                "tmux_window_id": kwargs["tmux_window_id"],
                "tmux_window_index": kwargs["tmux_window_index"],
                "derived_context": kwargs["derived_context"],
            },
        )()

    def fake_clone(source_window_id, target_window_id, *, source_cwd=None, isolate_sessions=False):
        events.append(("clone", source_window_id, source_cwd, isolate_sessions))
        return type(
            "CloneResult",
            (),
            {
                "cloned_agents": ("claude",),
                "session_ids": {"claude": "cloned-claude-session"},
                "resume_commands": {"claude": "claude --resume cloned-claude-session"},
            },
        )()

    monkeypatch.setattr("app.services.terminal_artifacts.create_window", fake_create_window)
    monkeypatch.setattr("app.services.terminal_artifacts.clone_window_agent_homes", fake_clone)

    client = type("Client", (), {"id": "client-1", "runtime": ClientRuntime.local})()
    source_window = type(
        "SourceWindow",
        (),
        {
            "id": "source-window",
            "title": "Source",
            "cwd": "/workspace",
            "shell_command": "claude",
            "folder_id": None,
            "root_window_id": None,
        },
    )()
    artifact = type("Artifact", (), {"id": "artifact-1", "artifact_kind": "agent_trace_graph"})()

    window = await _create_ephemeral_window(
        object(),
        client,
        source_window,
        artifact,
        tmux_manager=FakeTmuxManager(),
        registry=None,
    )

    assert events[0] == ("clone", "source-window", "/workspace", True)
    assert events[1] == ("tmux", "claude --resume cloned-claude-session")
    assert window.tmux_window_index == "4"
    assert window.derived_context["resume_commands"] == {"claude": "claude --resume cloned-claude-session"}

@pytest.mark.asyncio
async def test_create_ephemeral_local_window_uses_resolved_agent_command(monkeypatch) -> None:
    events = []

    class FakeTmuxManager:
        async def create_window(self, cwd, shell_command, *, client_id, window_id):
            events.append(("tmux", shell_command))
            return type(
                "Target",
                (),
                {
                    "session": "pool",
                    "window_id": "@3",
                    "window_index": "5",
                    "cwd": cwd,
                    "shell_command": shell_command,
                },
            )()

    async def fake_create_window(session, client_id, cwd, shell_command, **kwargs):
        return type(
            "Window",
            (),
            {
                "id": kwargs["window_id"],
                "status": None,
                "tmux_session": kwargs["tmux_session"],
                "tmux_window_id": kwargs["tmux_window_id"],
                "tmux_window_index": kwargs["tmux_window_index"],
                "derived_context": kwargs["derived_context"],
            },
        )()

    def fake_clone(source_window_id, target_window_id, *, source_cwd=None, isolate_sessions=False):
        events.append(("clone", isolate_sessions))
        return type(
            "CloneResult",
            (),
            {
                "cloned_agents": ("codex",),
                "session_ids": {"codex": "cloned-codex-session"},
                "resume_commands": {"codex": "codex resume cloned-codex-session"},
            },
        )()

    monkeypatch.setattr("app.services.terminal_artifacts.create_window", fake_create_window)
    monkeypatch.setattr("app.services.terminal_artifacts.clone_window_agent_homes", fake_clone)

    client = type("Client", (), {"id": "client-1", "runtime": ClientRuntime.local})()
    source_window = type(
        "SourceWindow",
        (),
        {
            "id": "source-window",
            "title": "Source",
            "cwd": "/workspace",
            "shell_command": "/bin/zsh",
            "folder_id": None,
            "root_window_id": None,
        },
    )()
    artifact = type("Artifact", (), {"id": "artifact-1", "artifact_kind": "agent_trace_graph"})()

    window = await _create_ephemeral_window(
        object(),
        client,
        source_window,
        artifact,
        source_agent_command="codex",
        tmux_manager=FakeTmuxManager(),
        registry=None,
    )

    assert events == [("clone", True), ("tmux", "codex resume cloned-codex-session")]
    assert window.tmux_window_index == "5"
    assert window.derived_context["source_agent_command"] == "codex"

@pytest.mark.asyncio
async def test_create_ephemeral_remote_window_delegates_clone_to_remote_runtime(monkeypatch) -> None:
    events = []

    class FakeRemoteRuntime:
        def __init__(self, **kwargs):
            events.append(("runtime", kwargs["client_id"]))

        async def create_window(self, **kwargs):
            events.append(("create", kwargs["clone_source_window_id"]))
            events.append(("isolate", kwargs["isolate_clone_sessions"]))
            return type(
                "RuntimeWindow",
                (),
                {
                    "session_id": "remote-session",
                    "window_id": "remote-window",
                    "cwd": kwargs["cwd"],
                    "shell_command": kwargs["shell_command"],
                },
            )()

    async def fake_create_window(session, client_id, cwd, shell_command, **kwargs):
        events.append(("db", kwargs["window_id"]))
        return type(
            "Window",
            (),
            {
                "id": kwargs["window_id"],
                "status": None,
                "remote_session_id": kwargs["remote_session_id"],
                "remote_window_id": kwargs["remote_window_id"],
            },
        )()

    def fail_clone(*args, **kwargs):
        raise AssertionError("remote artifact generation must not clone server-local homes")

    monkeypatch.setattr("app.services.terminal_artifacts.RemoteRuntime", FakeRemoteRuntime)
    monkeypatch.setattr("app.services.terminal_artifacts.create_window", fake_create_window)
    monkeypatch.setattr("app.services.terminal_artifacts.clone_window_agent_homes", fail_clone)

    client = type("Client", (), {"id": "client-1", "runtime": ClientRuntime.remote})()
    source_window = type(
        "SourceWindow",
        (),
        {
            "id": "source-window",
            "title": "Source",
            "cwd": "/workspace",
            "shell_command": "codex",
            "folder_id": None,
            "root_window_id": None,
        },
    )()
    artifact = type("Artifact", (), {"id": "artifact-1", "artifact_kind": "agent_trace_graph"})()

    window = await _create_ephemeral_window(
        object(),
        client,
        source_window,
        artifact,
        tmux_manager=object(),
        registry=object(),
    )

    assert window.remote_session_id == "remote-session"
    assert events[0][0] == "runtime"
    assert events[1] == ("create", "source-window")
    assert events[2] == ("isolate", True)
    assert events[3][0] == "db"

@pytest.mark.asyncio
async def test_artifact_running_invalidation_refreshes_window_state() -> None:
    events = []

    class FakeUiEventHub:
        async def publish_invalidation(self, resources, *, client_id, window_id, reason):
            events.append((resources, client_id, window_id, reason))

    artifact = type(
        "Artifact",
        (),
        {
            "client_id": uuid4(),
            "virtual_window_id": uuid4(),
        },
    )()

    await _publish_artifact_invalidation(FakeUiEventHub(), artifact, reason="artifact_running")

    assert events == [
        (
            ["terminal_artifacts", "project_todos", "window"],
            artifact.client_id,
            artifact.virtual_window_id,
            "artifact_running",
        )
    ]
