from __future__ import annotations

import sys

from app.contexts.windows.application import window_cloning as _window_cloning

sys.modules[__name__] = _window_cloning
