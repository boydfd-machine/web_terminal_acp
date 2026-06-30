from __future__ import annotations

import sys

from app.platform import auth_routes as _auth_routes

sys.modules[__name__] = _auth_routes
