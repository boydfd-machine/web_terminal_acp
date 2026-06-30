from __future__ import annotations

import sys

from app.platform.ingest import claude_watcher as _claude_watcher

sys.modules[__name__] = _claude_watcher
