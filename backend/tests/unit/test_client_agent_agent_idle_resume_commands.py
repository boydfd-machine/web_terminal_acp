from tests.unit.test_client_agent_agent_idle_support import *

@pytest.mark.asyncio
async def test_resume_window_sends_resume_command_and_clears_record(tmp_path: Path) -> None:
    runtime = FakeRuntime()
    supervisor = AgentIdleSupervisor(
        terminal=FakeTerminal(),
        runtime=runtime,
        suspension_dir=tmp_path,
    )
    record = SuspendedAgent(
        provider="claude_code",
        session_id="claude-session",
        command_name="claude",
        cwd="/workspace/project/.claude/worktrees/feature-blog",
        source_path=None,
        last_output_at=1,
        suspended_at=2,
        claude_worktree_name="feature-blog",
        claude_worktree_original_cwd="/workspace/project",
    )
    (tmp_path / f"{WINDOW_ID}.json").write_text(
        json.dumps({"window_id": str(WINDOW_ID), "agents": [record.__dict__]}),
        encoding="utf-8",
    )

    await supervisor.resume_window(WINDOW_ID)

    assert runtime.calls == [
        [
            "tmux",
            "send-keys",
            "-t",
            "pool:@7",
            "--",
            "cd /workspace/project && WEB_TERMINAL_AUTO_RESUME=1 claude --dangerously-skip-permissions --resume claude-session",
            "C-m",
        ]
    ]
    assert not (tmp_path / f"{WINDOW_ID}.json").exists()

def test_resume_command_formats_provider_commands() -> None:
    assert (
        resume_command(
            SuspendedAgent("codex", "codex-session", "codex", "/repo", None, 1, 2)
        )
        == "cd /repo && WEB_TERMINAL_AUTO_RESUME=1 codex --dangerously-bypass-approvals-and-sandbox resume codex-session"
    )
    assert (
        resume_command(
            SuspendedAgent("cursor_cli", "cursor-session", "cursor-agent", "/repo", None, 1, 2)
        )
        == "cd /repo && WEB_TERMINAL_AUTO_RESUME=1 cursor-agent --resume cursor-session"
    )
    assert (
        resume_command(
            SuspendedAgent("codex", "codex-session", "acpx", "/repo", None, 1, 2)
        )
        == "cd /repo && WEB_TERMINAL_AUTO_RESUME=1 codex --dangerously-bypass-approvals-and-sandbox resume codex-session"
    )
    assert (
        resume_command(
            SuspendedAgent(
                "antigravity_cli",
                "antigravity-session",
                "agy-p",
                "/repo",
                None,
                1,
                2,
            )
        )
        == "cd /repo && WEB_TERMINAL_AUTO_RESUME=1 agy-p --dangerously-skip-permissions --conversation antigravity-session"
    )

def test_resume_command_marks_auto_resume_without_cwd() -> None:
    assert (
        resume_command(
            SuspendedAgent("claude_code", "claude-session", "claude", None, None, 1, 2)
        )
        == "WEB_TERMINAL_AUTO_RESUME=1 claude --dangerously-skip-permissions --resume claude-session"
    )

def test_resume_command_ignores_claude_worktree_name() -> None:
    assert (
        resume_command(
            SuspendedAgent(
                "claude_code",
                "claude-session",
                "claude",
                "/repo/.claude/worktrees/feature",
                None,
                1,
                2,
                claude_worktree_name="feature",
                claude_worktree_original_cwd="/repo",
            )
        )
        == "cd /repo && WEB_TERMINAL_AUTO_RESUME=1 claude --dangerously-skip-permissions --resume claude-session"
    )
