from __future__ import annotations

import sys

from app.contexts.windows.domain import clone_spec as _clone_spec

sys.modules[__name__] = _clone_spec
