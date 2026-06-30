from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class LocalTerminalSession:
    master_fd: int
    process: asyncio.subprocess.Process
    shadow_window_id: str | None = None
    shadow_view_id: str | None = None
    task: asyncio.Task[None] | None = None
    selection_task: asyncio.Task[None] | None = None
    cleanup_started: bool = False
    size: tuple[int, int] | None = None
    output_buffer: bytearray = field(default_factory=bytearray)
    output_event: asyncio.Event = field(default_factory=asyncio.Event)
    output_eof: bool = False
    reader_task: asyncio.Task[None] | None = None
    resize_task: asyncio.Task[None] | None = None
