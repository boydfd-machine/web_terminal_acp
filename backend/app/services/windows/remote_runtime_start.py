from __future__ import annotations

import sys

from app.contexts.windows.application import remote_runtime_start as _remote_runtime_start

sys.modules[__name__] = _remote_runtime_start
