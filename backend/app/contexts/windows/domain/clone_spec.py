from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CloneReservation:
    cloned_agents: tuple[str, ...]
    session_ids: dict[str, str]
    resume_commands: dict[str, str]

    @classmethod
    def from_result(cls, result: object) -> "CloneReservation":
        return cls(
            cloned_agents=tuple(getattr(result, "cloned_agents", ())),
            session_ids=dict(getattr(result, "session_ids", {})),
            resume_commands=dict(getattr(result, "resume_commands", {})),
        )


@dataclass(frozen=True)
class WindowCloneSource:
    id: UUID
    cwd: str | None
    shell_command: str | None
    folder_id: UUID | None
    title: str
    title_manually_overridden: bool
    folder_manually_overridden: bool
    root_window_id: UUID | None

    @property
    def effective_root_window_id(self) -> UUID:
        return self.root_window_id or self.id


@dataclass(frozen=True)
class WindowCloneSpec:
    cwd: str | None
    shell_command: str | None
    folder_id: UUID | None
    title: str
    title_manually_overridden: bool
    folder_manually_overridden: bool
    parent_window_id: UUID
    root_window_id: UUID
    derived_mode: str
    derived_context: dict[str, object]

    @classmethod
    def remote(cls, source_window: WindowCloneSource, payload: object) -> "WindowCloneSpec":
        return cls._from_source(
            source_window,
            payload,
            shell_command=source_window.shell_command,
            agent_metadata={},
        )

    @classmethod
    def local(
        cls,
        source_window: WindowCloneSource,
        payload: object,
        reservation: CloneReservation,
        shell_command: str,
    ) -> "WindowCloneSpec":
        return cls._from_source(
            source_window,
            payload,
            shell_command=shell_command,
            agent_metadata={
                "cloned_agents": list(reservation.cloned_agents),
                "session_ids": reservation.session_ids,
                "resume_commands": reservation.resume_commands,
            },
        )

    @classmethod
    def _from_source(
        cls,
        source_window: WindowCloneSource,
        payload: object,
        *,
        shell_command: str | None,
        agent_metadata: dict[str, object],
    ) -> "WindowCloneSpec":
        mode = getattr(payload, "mode")
        derived_context: dict[str, object] = {
            "source_window_id": str(source_window.id),
            "mode": mode,
            **agent_metadata,
            "reserved": {
                "prompt": getattr(payload, "prompt", None),
                "collect_paths": getattr(payload, "collect_paths", None),
            },
        }
        return cls(
            cwd=source_window.cwd,
            shell_command=shell_command,
            folder_id=source_window.folder_id,
            title=f"{source_window.title} copy",
            title_manually_overridden=source_window.title_manually_overridden,
            folder_manually_overridden=source_window.folder_manually_overridden,
            parent_window_id=source_window.id,
            root_window_id=source_window.effective_root_window_id,
            derived_mode=mode,
            derived_context=derived_context,
        )
