from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID

import app.client_agent.runner.resume_policy as resume_policy
from app.client_agent.agent_idle import AgentIdleSupervisor
from app.client_agent.runtime_window import ClientRuntimeWindow
from app.client_agent.terminal import ClientTerminalMultiplexer
from app.client_agent.tmux_runtime import ClientTmuxRuntime


@dataclass(frozen=True)
class RuntimeWindowAvailability:
    window: ClientRuntimeWindow
    resume_decision: resume_policy.ResumeDecision


async def ensure_runtime_window_available(
    runtime: ClientTmuxRuntime,
    terminal: ClientTerminalMultiplexer,
    idle_supervisor: AgentIdleSupervisor,
    window_id: UUID,
    *,
    remote_session_id: str,
    remote_window_id: str,
    cwd: str | None = None,
    shell_command: str | None = None,
    allow_missing_window_recreate: bool = False,
) -> RuntimeWindowAvailability:
    registered = getattr(terminal, "registered_remote_window", lambda _window_id: None)(window_id)
    if registered is not None and registered != (remote_session_id, remote_window_id):
        remote_session_id, remote_window_id = registered
    if await runtime.has_window(remote_window_id, remote_session_id=remote_session_id):
        runtime_window = ClientRuntimeWindow(
            remote_session_id=remote_session_id,
            remote_window_id=remote_window_id,
            local_window_id=window_id,
            cwd=cwd,
            shell_command=shell_command,
            managed_agent_tools=True,
        )
        resume_decision = resume_policy.NO_RESUME
        if idle_supervisor.has_resumable_session(window_id, project_path=cwd):
            resume_decision = await resume_policy.existing_window_resume_decision(
                runtime,
                runtime_window,
            )
    else:
        runtime_window, resume_decision = await _recreate_missing_runtime_window(
            runtime,
            terminal,
            idle_supervisor,
            window_id,
            remote_session_id=remote_session_id,
            remote_window_id=remote_window_id,
            cwd=cwd,
            shell_command=shell_command,
            allow_missing_window_recreate=allow_missing_window_recreate,
        )

    return _register_available_window(
        terminal,
        idle_supervisor,
        window_id,
        runtime_window,
        resume_decision,
    )


async def _recreate_missing_runtime_window(
    runtime: ClientTmuxRuntime,
    terminal: ClientTerminalMultiplexer,
    idle_supervisor: AgentIdleSupervisor,
    window_id: UUID,
    *,
    remote_session_id: str,
    remote_window_id: str,
    cwd: str | None,
    shell_command: str | None,
    allow_missing_window_recreate: bool,
) -> tuple[ClientRuntimeWindow, resume_policy.ResumeDecision]:
    terminal.unregister_window(window_id)
    if not allow_missing_window_recreate:
        raise RuntimeError(f"missing tmux window for {window_id}: {remote_session_id}:{remote_window_id}")
    should_resume_session = idle_supervisor.has_resumable_session(window_id, project_path=cwd)
    recreation = await runtime.recreate_window_with_status(
        window_id,
        cwd=cwd,
        shell_command=None if should_resume_session else shell_command,
    )
    runtime_window = recreation.window
    resume_decision = resume_policy.NO_RESUME
    if should_resume_session:
        runtime_window = replace(runtime_window, shell_command=shell_command)
        if recreation.created:
            resume_decision = resume_policy.LATEST_SESSION_RESUME
    return runtime_window, resume_decision


def _register_available_window(
    terminal: ClientTerminalMultiplexer,
    idle_supervisor: AgentIdleSupervisor,
    window_id: UUID,
    runtime_window: ClientRuntimeWindow,
    resume_decision: resume_policy.ResumeDecision,
) -> RuntimeWindowAvailability:
    terminal.register_window(
        window_id,
        runtime_window.remote_session_id,
        runtime_window.remote_window_id,
    )
    idle_supervisor.register_window(window_id, runtime_window.cwd)
    return RuntimeWindowAvailability(window=runtime_window, resume_decision=resume_decision)
