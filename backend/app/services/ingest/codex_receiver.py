from __future__ import annotations

import sys

from app.platform.ingest import codex_receiver as _codex_receiver

sys.modules[__name__] = _codex_receiver
