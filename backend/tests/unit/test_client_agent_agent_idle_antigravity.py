from tests.unit.test_client_agent_agent_idle_support import *


def _antigravity_transcript(root: Path, session_id: str = "antigravity-session") -> Path:
    return root / "brain" / session_id / ".system_generated" / "logs" / "transcript.jsonl"


def _write_antigravity_transcript(path: Path, *, session_id: str = "antigravity-session") -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"type": "PLANNER_RESPONSE", "session_id": session_id}) + "\n",
        encoding="utf-8",
    )


def test_antigravity_session_id_from_payload_and_transcript_path(tmp_path: Path) -> None:
    transcript = _antigravity_transcript(tmp_path / "antigravity")

    assert (
        session_id_from_payload(
            "antigravity_cli",
            {"type": "PLANNER_RESPONSE", "session_id": "antigravity-session"},
            None,
        )
        == "antigravity-session"
    )
    assert (
        session_id_from_payload("antigravity_cli", {"type": "PLANNER_RESPONSE"}, str(transcript))
        == "antigravity-session"
    )


def test_latest_antigravity_session_ref_reads_managed_transcripts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    antigravity_root = home / ".web-terminal-acp" / "antigravity-cli-homes" / str(WINDOW_ID)
    transcript = _antigravity_transcript(antigravity_root)
    _write_antigravity_transcript(transcript)
    os.utime(transcript, (3000, 3000))

    antigravity_ref = latest_antigravity_session_ref(WINDOW_ID)

    assert antigravity_ref is not None
    assert antigravity_ref.session_id == "antigravity-session"
    assert antigravity_ref.source_path == str(transcript)


def test_latest_resume_command_uses_antigravity_conversation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    antigravity_root = home / ".web-terminal-acp" / "antigravity-cli-homes" / str(WINDOW_ID)
    _write_antigravity_transcript(_antigravity_transcript(antigravity_root))

    assert (
        latest_resume_command(WINDOW_ID, project_path="/workspace/project")
        == "cd /workspace/project && WEB_TERMINAL_AUTO_RESUME=1 agy-p --dangerously-skip-permissions --conversation antigravity-session"
    )


@pytest.mark.asyncio
async def test_idle_supervisor_suspends_antigravity_after_one_hour(tmp_path: Path) -> None:
    now = 10_000.0
    terminated: list[tuple[AgentProcess, ...]] = []
    transcript = _antigravity_transcript(tmp_path / "antigravity")
    _write_antigravity_transcript(transcript)
    os.utime(transcript, (now - 3601, now - 3601))
    process = AgentProcess(
        provider="antigravity_cli",
        pid=123,
        cmdline="agy-p",
        command_name="agy-p",
        cwd="/workspace/project",
    )

    async def detector(window_id, terminal, runtime):
        return {"antigravity_cli": (process,)}

    async def terminator(processes):
        terminated.append(processes)

    supervisor = AgentIdleSupervisor(
        terminal=FakeTerminal(),
        runtime=FakeRuntime(),
        idle_seconds=3600,
        suspension_dir=tmp_path / "suspensions",
        clock=lambda: now,
        process_detector=detector,
        process_terminator=terminator,
    )
    await supervisor.observe_events(
        [
            ManagedAiEvent(
                provider="antigravity_cli",
                client_id=CLIENT_ID,
                window_id=WINDOW_ID,
                source_path=str(transcript),
                offset=0,
                cursor=0,
                project_path="/workspace/project",
                payload={
                    "type": "PLANNER_RESPONSE",
                    "session_id": "antigravity-session",
                },
            )
        ]
    )

    await supervisor.maybe_suspend_window(WINDOW_ID)

    assert terminated == [(process,)]
    payload = json.loads(
        (tmp_path / "suspensions" / f"{WINDOW_ID}.json").read_text(encoding="utf-8")
    )
    assert payload["agents"][0]["provider"] == "antigravity_cli"
    assert payload["agents"][0]["session_id"] == "antigravity-session"
    assert payload["agents"][0]["command_name"] == "agy-p"
