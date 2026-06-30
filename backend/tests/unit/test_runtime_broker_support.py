import asyncio

from uuid import UUID, uuid4

import pytest

from app.services.runtime import broker as broker_module

from app.services.runtime.broker import TerminalBroker, terminal_status_message

from app.services.runtime.types import RuntimeFileEntry, RuntimeWindow

async def _unsubscribe_remaining_output_senders(
    broker: TerminalBroker,
    client_id: UUID,
    window_id: UUID,
) -> None:
    for sender in tuple(broker._subscribers.get((client_id, window_id), {})):
        await broker.unsubscribe(client_id, window_id, sender)

class FakeRuntime:
    def __init__(self) -> None:
        self.created: list[tuple[str | None, str | None]] = []
        self.attached: list[RuntimeWindow] = []
        self.detached: list[RuntimeWindow] = []
        self.attached_local_window_ids = []
        self.detached_local_window_ids = []
        self.attached_view_ids = []
        self.attach_recreate_permissions = []
        self.detached_view_ids = []
        self.inputs: list[tuple[RuntimeWindow, bytes]] = []
        self.input_view_ids = []
        self.direct_inputs: list[tuple[RuntimeWindow, bytes]] = []
        self.direct_input_local_window_ids = []
        self.resizes: list[tuple[RuntimeWindow, int, int]] = []
        self.resize_view_ids = []
        self.captures: list[RuntimeWindow] = []
        self.capture_local_window_ids = []
        self.capture_view_ids = []
        self.capture_history_lines = []
        self.file_reads: list[tuple[str, int | None]] = []
        self.file_lists: list[str] = []
        self.file_writes: list[tuple[str, bytes, bool]] = []
        self.selections: list[tuple[RuntimeWindow, RuntimeWindow]] = []
        self.selection_view_ids = []
        self.selection_recreate_permissions = []
        self.detach_started = asyncio.Event()
        self.allow_detach: asyncio.Event | None = None
        self.attach_result: RuntimeWindow | None = None
        self.selection_result: RuntimeWindow | None = None

    async def create_window(
        self, cwd: str | None = None, shell_command: str | None = None
    ) -> RuntimeWindow:
        self.created.append((cwd, shell_command))
        return RuntimeWindow(session_id="session", window_id="@1")

    async def attach(
        self,
        window: RuntimeWindow,
        sender,
        *,
        local_window_id=None,
        selection_callback=None,
        view_id=None,
        allow_missing_window_recreate=False,
    ) -> None:
        self.attached.append(window)
        self.attached_local_window_ids.append(local_window_id)
        self.attached_view_ids.append(view_id)
        self.attach_recreate_permissions.append(allow_missing_window_recreate)
        await sender(b"attached")
        return self.attach_result or window

    async def detach(self, window: RuntimeWindow, *, local_window_id=None, view_id=None) -> None:
        self.detach_started.set()
        self.detached_local_window_ids.append(local_window_id)
        self.detached_view_ids.append(view_id)
        if self.allow_detach is not None:
            await self.allow_detach.wait()
        self.detached.append(window)

    async def send_input(
        self, window: RuntimeWindow, data: bytes, *, local_window_id=None, view_id=None
    ) -> None:
        self.inputs.append((window, data))
        self.input_view_ids.append(view_id)

    async def send_input_direct(self, window: RuntimeWindow, data: bytes, *, local_window_id=None) -> None:
        self.direct_inputs.append((window, data))
        self.direct_input_local_window_ids.append(local_window_id)

    async def resize(self, window: RuntimeWindow, *, cols: int, rows: int, local_window_id=None, view_id=None) -> None:
        self.resizes.append((window, cols, rows))
        self.resize_view_ids.append(view_id)

    async def capture_output_bytes(
        self,
        window: RuntimeWindow,
        *,
        local_window_id=None,
        view_id=None,
        history_lines=None,
    ) -> bytes:
        self.captures.append(window)
        self.capture_local_window_ids.append(local_window_id)
        self.capture_view_ids.append(view_id)
        self.capture_history_lines.append(history_lines)
        return b"screen"

    async def read_file_bytes(self, path: str, *, max_bytes: int | None = None) -> bytes:
        self.file_reads.append((path, max_bytes))
        return b"file"

    async def list_file_entries(self, path: str) -> list[RuntimeFileEntry]:
        self.file_lists.append(path)
        return [RuntimeFileEntry(name="README.md", path="/tmp/README.md", kind="file", size=4)]

    async def write_file_bytes(self, path: str, data: bytes, *, overwrite: bool = True) -> None:
        self.file_writes.append((path, data, overwrite))

    async def select_window(
        self,
        current_window: RuntimeWindow,
        next_window: RuntimeWindow,
        *,
        local_window_id,
        view_id=None,
        allow_missing_window_recreate=False,
    ) -> None:
        self.selections.append((current_window, next_window))
        self.selection_view_ids.append(view_id)
        self.selection_recreate_permissions.append(allow_missing_window_recreate)
        return self.selection_result or next_window

__all__ = [name for name in globals() if not name.startswith("__")]
