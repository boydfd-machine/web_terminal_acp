from __future__ import annotations

import sys

from app.platform import search_routes as _search_routes

sys.modules[__name__] = _search_routes
