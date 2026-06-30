from __future__ import annotations

import sys

from app.contexts.terminal_runtime.application import client_connections as _client_connections

sys.modules[__name__] = _client_connections
