from __future__ import annotations

import sys

from app.contexts.terminal_runtime.application import local_session as _local_session

sys.modules[__name__] = _local_session
