from __future__ import annotations

import sys

from app.contexts.terminal_runtime.application import offline_monitor as _offline_monitor

sys.modules[__name__] = _offline_monitor
