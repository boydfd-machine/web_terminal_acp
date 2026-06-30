from __future__ import annotations

import sys

from app.contexts.terminal_runtime.application import window_reconciler as _window_reconciler

sys.modules[__name__] = _window_reconciler
