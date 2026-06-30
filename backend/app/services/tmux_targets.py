from __future__ import annotations

import sys

from app.contexts.terminal_runtime.infrastructure import tmux_targets as _service

sys.modules[__name__] = _service
