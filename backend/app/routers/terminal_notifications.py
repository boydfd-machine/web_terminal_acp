from __future__ import annotations

import sys

from app.contexts.activity.api import terminal_notifications_routes as _routes

sys.modules[__name__] = _routes
