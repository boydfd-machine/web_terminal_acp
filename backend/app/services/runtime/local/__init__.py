from __future__ import annotations

import sys
from importlib import import_module

from app.contexts.terminal_runtime.infrastructure import local as _local

_pty_io = import_module("app.contexts.terminal_runtime.infrastructure.local.pty_io")
_output_pipe = import_module("app.contexts.terminal_runtime.infrastructure.local.output_pipe")
_runtime = import_module("app.contexts.terminal_runtime.infrastructure.local.runtime")

sys.modules[__name__] = _local
sys.modules[f"{__name__}.pty_io"] = _pty_io
sys.modules[f"{__name__}.output_pipe"] = _output_pipe
sys.modules[f"{__name__}.runtime"] = _runtime
