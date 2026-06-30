from __future__ import annotations

import sys

from app.contexts.workspace.application import summary_worker as _summary_worker

sys.modules[__name__] = _summary_worker
