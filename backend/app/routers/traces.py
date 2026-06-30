from __future__ import annotations

import sys

from app.contexts.activity.api import traces_routes as _routes

sys.modules[__name__] = _routes
