from __future__ import annotations

import sys

from app.contexts.workspace.api import folders_routes as _routes

sys.modules[__name__] = _routes
