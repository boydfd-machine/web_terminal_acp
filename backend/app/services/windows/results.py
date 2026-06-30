from __future__ import annotations

import sys

from app.contexts.windows.application import results as _results

sys.modules[__name__] = _results
