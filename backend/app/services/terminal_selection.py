from __future__ import annotations

import sys

from app.contexts.terminal_runtime.application import selection as _service

sys.modules[__name__] = _service
