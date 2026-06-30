from __future__ import annotations

import sys

from app.platform import search_index as _search_index

sys.modules[__name__] = _search_index
