from __future__ import annotations

import sys

from app.platform import ingest as _ingest
from app.platform.ingest import claude_watcher as _claude_watcher
from app.platform.ingest import codex_receiver as _codex_receiver
from app.platform.ingest import normalizers as _normalizers

sys.modules[__name__] = _ingest
sys.modules[f"{__name__}.claude_watcher"] = _claude_watcher
sys.modules[f"{__name__}.codex_receiver"] = _codex_receiver
sys.modules[f"{__name__}.normalizers"] = _normalizers
