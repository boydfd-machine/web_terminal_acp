from __future__ import annotations

import sys

from app.contexts.windows.application import local_runtime_start as _local_runtime_start

sys.modules[__name__] = _local_runtime_start
