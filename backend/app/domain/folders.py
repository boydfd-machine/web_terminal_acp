from __future__ import annotations

import sys

from app.contexts.workspace.domain import folders as _folders

sys.modules[__name__] = _folders
