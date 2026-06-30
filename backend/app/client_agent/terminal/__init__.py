from __future__ import annotations

import asyncio
import os
import pty
import select
import signal
import sys
from types import ModuleType

from app.client_agent.terminal.common import (
    DIRECT_INPUT_SUBMIT_DELAY_SECONDS,
    PTY_DRAIN_BUFFER_MAX_BYTES,
    PTY_OUTPUT_SEND_CHUNK_BYTES,
    PTY_READ_CHUNK_BYTES,
    Runner,
    SELECTION_POLL_INTERVAL_SECONDS,
    SelectionSender,
    TerminalSender,
    _AttachedTerminal,
    _RemoteTarget,
    _apply_pty_resize,
    _attach_process_environment,
    _configure_pty_slave,
    _run_pty_control,
)
from app.client_agent.terminal.private_ops import ClientTerminalPrivateOps
from app.client_agent.terminal.public_ops import ClientTerminalPublicOps
from app.client_agent.terminal import common as _common_module
from app.client_agent.terminal import private_ops as _private_ops_module
from app.client_agent.terminal import public_ops as _public_ops_module



class ClientTerminalMultiplexer(ClientTerminalPublicOps, ClientTerminalPrivateOps):
    def __init__(self, *, runner: Runner | None = None) -> None:
        self._runner = runner
        self._windows: dict[str, _RemoteTarget] = {}
        self._attached: dict[str, _AttachedTerminal] = {}
        self._attachment_windows: dict[str, str] = {}
        self._lock = asyncio.Lock()


_COMPAT_MODULES = (_common_module, _private_ops_module, _public_ops_module)


class _TerminalModule(ModuleType):
    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        for module in _COMPAT_MODULES:
            if name in module.__dict__:
                setattr(module, name, value)


sys.modules[__name__].__class__ = _TerminalModule

__all__ = [
    "ClientTerminalMultiplexer",
    "DIRECT_INPUT_SUBMIT_DELAY_SECONDS",
    "PTY_DRAIN_BUFFER_MAX_BYTES",
    "PTY_OUTPUT_SEND_CHUNK_BYTES",
    "PTY_READ_CHUNK_BYTES",
    "Runner",
    "SELECTION_POLL_INTERVAL_SECONDS",
    "SelectionSender",
    "TerminalSender",
    "os",
    "pty",
    "select",
    "signal",
    "_apply_pty_resize",
    "_attach_process_environment",
    "_configure_pty_slave",
    "_run_pty_control",
]
