from __future__ import annotations

import sys

from app.contexts.terminal_runtime.infrastructure import pty_control as _pty_control

sys.modules[__name__] = _pty_control
