from __future__ import annotations

import sys

from app.platform.ingest import normalizers as _normalizers

sys.modules[__name__] = _normalizers
