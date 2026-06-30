# ruff: noqa: F403, F405
from tests.unit.test_terminal_artifact_service_support import *

from app.models import ProjectTodo, ProjectTodoArtifact, ProjectTodoStatus

@pytest.mark.asyncio
async def test_run_artifact_prompt_sends_codex_followup_submits_while_waiting_for_file(
    monkeypatch,
) -> None:
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_AGENT_READY_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_AGENT_READY_SETTLE_SECONDS", 0.0)
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_OUTPUT_FILE_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(
        terminal_artifact_service,
        "ARTIFACT_CODEX_FOLLOWUP_SUBMIT_INTERVAL_SECONDS",
        0.01,
    )
    monkeypatch.setattr(
        terminal_artifact_service,
        "ARTIFACT_CODEX_FOLLOWUP_SUBMIT_DURATION_SECONDS",
        1.0,
    )
    inputs = []

    class FakeBroker:
        def runtime_for(self, client_id):
            return object()

        async def capture_output_bytes(self, client_id, window_id, runtime_window, *, history_lines=None):
            assert history_lines == terminal_artifact_service.ARTIFACT_CAPTURE_HISTORY_LINES
            return b"OpenAI Codex (v0.136.0)\nmodel:       gpt-5.5 xhigh\n\n\xe2\x80\xba "

        async def send_input_direct(self, client_id, window_id, runtime_window, data):
            inputs.append(data)

        async def read_file_bytes(self, client_id, path, *, max_bytes=None):
            if len(inputs) >= 3:
                return b'{"task":"demo","goals":[],"nodes":[],"edges":[]}'
            raise FileNotFoundError(path)

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
        output_path="/tmp/web-terminal-artifact.json",
        is_complete=lambda value: '"task":"demo"' in value,
        session_factory=unused_session_factory,
        terminal_broker=FakeBroker(),
        tmux_manager=object(),
        registry=None,
    )

    assert output == '{"task":"demo","goals":[],"nodes":[],"edges":[]}'
    assert inputs[0] == b"artifact prompt\x1b[13u"
    assert len(inputs) >= 3
    assert all(
        data == terminal_artifact_service.ARTIFACT_CODEX_COMPOSER_SUBMIT_INPUT
        for data in inputs[1:]
    )

@pytest.mark.asyncio
async def test_read_artifact_output_file_ignores_incomplete_json(monkeypatch) -> None:
    monkeypatch.setattr(terminal_artifact_service, "ARTIFACT_OUTPUT_FILE_POLL_INTERVAL_SECONDS", 0.01)
    reads = []

    class FakeBroker:
        async def read_file_bytes(self, client_id, path, *, max_bytes=None):
            reads.append(path)
            if len(reads) == 1:
                return b'{"task":"demo"'
            return b'{"task":"demo","goals":[],"nodes":[],"edges":[]}'

    output = await _read_artifact_output_file(
        FakeBroker(),
        "client-1",
        "/tmp/artifact.json",
        is_complete=lambda value: '"edges":[]' in value,
        timeout_seconds=1,
    )

    assert output == '{"task":"demo","goals":[],"nodes":[],"edges":[]}'
    assert reads == ["/tmp/artifact.json", "/tmp/artifact.json"]

def test_command_bytes_for_prompt_rejects_non_agent_shell() -> None:
    with pytest.raises(ValueError, match="interactive agent terminal"):
        terminal_artifact_service._command_bytes_for_prompt("/bin/bash", "artifact prompt")

def test_command_bytes_for_prompt_uses_codex_composer_submit() -> None:
    assert (
        terminal_artifact_service._command_bytes_for_prompt("codex", "artifact prompt")
        == b"artifact prompt\x1b[13u"
    )


def test_command_bytes_for_prompt_uses_claude_bracketed_paste_and_enter_submit() -> None:
    assert (
        terminal_artifact_service._command_bytes_for_prompt("claude", "line one\nline two")
        == b"\x1b[200~line one\nline two\x1b[201~\n"
    )

@pytest.mark.asyncio
async def test_resolve_source_agent_command_uses_latest_agent_terminal_command() -> None:
    class FakeSession:
        async def scalar(self, statement):
            return {"command": "codex"}

    source_window = type(
        "SourceWindow",
        (),
        {
            "id": uuid4(),
            "client_id": uuid4(),
            "shell_command": "/bin/zsh",
        },
    )()

    command = await _resolve_source_agent_command(FakeSession(), source_window)

    assert command == "codex"

@pytest.mark.asyncio
async def test_resolve_source_agent_command_uses_ai_session_when_latest_input_is_prompt() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.calls = 0

        async def scalar(self, statement):
            self.calls += 1
            if self.calls == 1:
                return {"command": "hi"}
            return type("AiSession", (), {"provider": "codex"})()

    source_window = type(
        "SourceWindow",
        (),
        {
            "id": uuid4(),
            "client_id": uuid4(),
            "shell_command": "/bin/zsh",
        },
    )()

    command = await _resolve_source_agent_command(FakeSession(), source_window)

    assert command == "codex"
