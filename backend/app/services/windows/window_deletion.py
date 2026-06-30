from __future__ import annotations

import sys

from app.contexts.windows.application import window_deletion as _window_deletion

sys.modules[__name__] = _window_deletion
