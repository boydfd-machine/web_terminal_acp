from __future__ import annotations

import sys
from importlib import import_module

from app.contexts.terminal_runtime import api as _api

_runtime_dependencies = import_module("app.contexts.terminal_runtime.api.runtime_dependencies")
_terminal_websocket = import_module("app.contexts.terminal_runtime.api.terminal_websocket")
_selection_websocket = import_module("app.contexts.terminal_runtime.api.selection_websocket")

sys.modules[__name__] = _api
sys.modules[f"{__name__}.runtime_dependencies"] = _runtime_dependencies
sys.modules[f"{__name__}.terminal_websocket"] = _terminal_websocket
sys.modules[f"{__name__}.selection_websocket"] = _selection_websocket
