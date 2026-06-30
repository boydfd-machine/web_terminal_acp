from __future__ import annotations

import sys

from app.contexts.workspace.application import summarizer as _summarizer

sys.modules[__name__] = _summarizer
