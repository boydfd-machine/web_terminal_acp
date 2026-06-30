from __future__ import annotations

import sys

from app.contexts.windows.application import errors as _errors

sys.modules[__name__] = _errors
