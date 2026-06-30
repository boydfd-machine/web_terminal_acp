from __future__ import annotations

import sys

from app.contexts.terminal_runtime.application import connection_registry as _connection_registry

sys.modules[__name__] = _connection_registry
