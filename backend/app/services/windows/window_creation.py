from __future__ import annotations

import sys

from app.contexts.windows.application import window_creation as _window_creation

sys.modules[__name__] = _window_creation
