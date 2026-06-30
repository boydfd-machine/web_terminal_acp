from __future__ import annotations

import sys

from app.platform import cache_backend as _cache_backend

sys.modules[__name__] = _cache_backend
