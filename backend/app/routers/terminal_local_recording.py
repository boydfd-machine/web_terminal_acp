from __future__ import annotations

import sys

from app.contexts.terminal_runtime.api import local_recording_routes as _routes

sys.modules[__name__] = _routes
