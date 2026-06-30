from __future__ import annotations

import sys

from app.shared import redaction as _redaction

sys.modules[__name__] = _redaction
