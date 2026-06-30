from __future__ import annotations

import sys

from app.contexts.workspace.application import folder_splitter as _service

sys.modules[__name__] = _service
