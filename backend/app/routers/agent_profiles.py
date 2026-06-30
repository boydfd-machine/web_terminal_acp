from __future__ import annotations

import sys

from app.contexts.agent_profiles.api import routes as _routes

sys.modules[__name__] = _routes
