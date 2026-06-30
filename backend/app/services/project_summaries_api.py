from __future__ import annotations

import sys

from app.contexts.workspace.application import project_summaries_service as _service

sys.modules[__name__] = _service
