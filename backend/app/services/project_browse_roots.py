from __future__ import annotations

import sys

from app.contexts.workspace.application import project_browse_roots as _service

sys.modules[__name__] = _service
