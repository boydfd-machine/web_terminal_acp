from __future__ import annotations

import sys

from app.contexts.terminal_runtime.domain import protocol as _protocol

sys.modules[__name__] = _protocol
