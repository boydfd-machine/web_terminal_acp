from __future__ import annotations

import sys

from app.contexts.terminal_runtime.application import aux_terminal as _aux_terminal

sys.modules[__name__] = _aux_terminal
