from __future__ import annotations

import sys

from app.contexts.activity.application import window_activity as _service

sys.modules[__name__] = _service
