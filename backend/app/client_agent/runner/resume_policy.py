from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.client_agent.agent_work_presence import detect_agent_processes_for_tmux_target
from app.client_agent.runtime_window import ClientRuntimeWindow
from app.client_agent.tmux_runtime import ClientTmuxRuntime

SHELL_COMMAND_NAMES = frozenset({
    "bash",
    "csh",
    "dash",
    "fish",
    "ksh",
    "mksh",
    "nu",
    "pwsh",
    "sh",
    "tcsh",
    "xonsh",
    "zsh",
})


@dataclass(frozen=True)
class ResumeDecision:
    should_resume: bool
    allow_latest_session: bool = False


NO_RESUME = ResumeDecision(False)
SUSPENDED_ONLY_RESUME = ResumeDecision(True)
LATEST_SESSION_RESUME = ResumeDecision(True, allow_latest_session=True)


async def existing_window_resume_decision(
    runtime: ClientTmuxRuntime,
    window: ClientRuntimeWindow,
) -> ResumeDecision:
    tmux_target = f"{window.remote_session_id}:{window.remote_window_id}"
    if await detect_agent_processes_for_tmux_target(tmux_target, runtime=runtime):
        return NO_RESUME
    if not await _target_foreground_is_shell(runtime, tmux_target):
        return NO_RESUME
    return SUSPENDED_ONLY_RESUME


async def resume_window_from_decision(
    idle_supervisor,
    window_id: UUID,
    decision: ResumeDecision,
) -> None:
    if not decision.should_resume:
        return
    await idle_supervisor.resume_window(
        window_id,
        allow_latest_session=decision.allow_latest_session,
    )


async def resume_existing_window_if_safe(
    runtime: ClientTmuxRuntime,
    terminal,
    idle_supervisor,
    window_id: UUID,
) -> None:
    registered = getattr(terminal, "registered_remote_window", lambda _window_id: None)(window_id)
    if registered is None:
        return
    remote_session_id, remote_window_id = registered
    decision = await existing_window_resume_decision(
        runtime,
        ClientRuntimeWindow(
            remote_session_id=remote_session_id,
            remote_window_id=remote_window_id,
            local_window_id=window_id,
        ),
    )
    await resume_window_from_decision(idle_supervisor, window_id, decision)


async def _target_foreground_is_shell(runtime: ClientTmuxRuntime, tmux_target: str) -> bool:
    try:
        output = await runtime._run(
            [
                "tmux",
                "display-message",
                "-p",
                "-t",
                tmux_target,
                "#{pane_current_command}",
            ]
        )
    except Exception:
        return False
    command_name = Path(output.strip()).name.lower()
    return command_name in _shell_command_names(runtime)


def _shell_command_names(runtime: ClientTmuxRuntime) -> frozenset[str]:
    names = set(SHELL_COMMAND_NAMES)
    try:
        default_shell = shlex.split(runtime.default_shell)[0]
    except (AttributeError, IndexError, ValueError):
        default_shell = ""
    default_shell_name = Path(default_shell).name.lower()
    if default_shell_name:
        names.add(default_shell_name)
    return frozenset(names)
