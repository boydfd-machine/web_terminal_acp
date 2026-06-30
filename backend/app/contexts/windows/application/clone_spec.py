from __future__ import annotations

from app.contexts.windows.domain.clone_spec import WindowCloneSource
from app.models import VirtualWindow


def clone_source_from_model(window: VirtualWindow) -> WindowCloneSource:
    return WindowCloneSource(
        id=window.id,
        cwd=window.cwd,
        shell_command=window.shell_command,
        folder_id=window.folder_id,
        title=window.title,
        title_manually_overridden=window.title_manually_overridden,
        folder_manually_overridden=window.folder_manually_overridden,
        root_window_id=window.root_window_id,
    )
