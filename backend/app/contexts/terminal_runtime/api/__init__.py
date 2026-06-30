from __future__ import annotations

import sys
from types import ModuleType

from app.contexts.terminal_runtime.api import runtime_dependencies as _runtime_dependencies
from app.contexts.terminal_runtime.api import selection_websocket as _selection_websocket
from app.contexts.terminal_runtime.api import terminal_websocket as _terminal_websocket

for _module in (_runtime_dependencies, _terminal_websocket, _selection_websocket):
    for _name, _value in _module.__dict__.items():
        if not _name.startswith("__"):
            globals().setdefault(_name, _value)

terminal_websocket = _terminal_websocket.terminal_websocket
local_terminal_websocket = _selection_websocket.local_terminal_websocket
terminal_selection_websocket = _selection_websocket.terminal_selection_websocket

_COMPAT_MODULES = (_runtime_dependencies, _terminal_websocket, _selection_websocket)


class _TerminalApiModule(ModuleType):
    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        for module in _COMPAT_MODULES:
            if name in module.__dict__:
                setattr(module, name, value)


sys.modules[__name__].__class__ = _TerminalApiModule

__all__ = [
    "local_terminal_websocket",
    "mark_window_active",
    "mark_window_disconnected",
    "mark_window_error",
    "router",
    "terminal_selection_websocket",
    "terminal_websocket",
]
