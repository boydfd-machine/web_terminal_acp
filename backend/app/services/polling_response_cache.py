from __future__ import annotations

import sys

from app.platform import polling_response_cache as _polling_response_cache

sys.modules[__name__] = _polling_response_cache
