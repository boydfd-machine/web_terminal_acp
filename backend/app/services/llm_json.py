from __future__ import annotations

import sys

from app.shared import llm_json as _llm_json

sys.modules[__name__] = _llm_json
