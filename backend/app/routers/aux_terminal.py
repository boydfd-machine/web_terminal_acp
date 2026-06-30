from __future__ import annotations

import sys

from app.contexts.terminal_runtime.api import aux_terminal_routes as _aux_terminal_routes

sys.modules[__name__] = _aux_terminal_routes
